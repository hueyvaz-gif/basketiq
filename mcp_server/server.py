"""
BasketIQ MCP serveri — layihənin funksiyalarını AI agentlərinə açır.

NİYƏ MCP?
FastAPI endpoint-lərini insan (dashboard) və skript çağırır. MCP isə eyni
funksiyaları MODELİN çağıra bilməsi üçün standart formatda təsvir edir:
alətin adı, nə etdiyi, hansı parametrləri var. n8n-in AI Agent node-u,
Claude Desktop və başqa MCP klientləri bu təsviri oxuyub özləri qərar verir
ki, "səbətim harada ucuzdur?" sualına hansı aləti çağırmaq lazımdır.

BİR MƏNTİQ, İKİ QAPI:
Alətlər öz məntiqini YAZMIR - `app/api/*` içindəki eyni funksiyaları çağırır.
Səbəb: müqayisə qaydası ("natamam market qalib elan edilmir") bir yerdə
qalmalıdır. İki nüsxə olsaydı, birini düzəldib digərini unutmaq işdən deyil.

CAVABLAR QISADIR:
Alətin qaytardığı hər simvol modelin konteksinə düşür. `compare()` funksiyası
onlarla sətirlik JSON qaytarır - onu olduğu kimi versək, model boş yerə yüklənər
və cavab yazması yavaşlayar (ölçülüb: cavab yazması 4.5 token/san). Ona görə
hər alət YALNIZ qərar üçün lazım olanı qaytarır.

BLOKLAMA:
Scraping və OCR dəqiqələrlə çəkən SİNXRON işdir. MCP serveri FastAPI ilə eyni
prosesdə işlədiyi üçün onu birbaşa çağırsaq, bütün veb tətbiq donar. Ona görə
ağır işlər `anyio.to_thread` ilə ayrıca sapda icra olunur.

İşə salmaq:
    python -m mcp_server.server            # stdio (Claude Desktop üçün)
    python -m mcp_server.server --http     # ayrıca HTTP serveri
    uvicorn app.main:app                   # FastAPI-yə qoşulmuş: /mcp
"""

import anyio
from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer

from ai.llm import check_llm
from app.api import basket, catalogs, products
from app.api.basket import BasketItemIn
from app.db import db_stats
from app.profile import Profile, get_profile, save_profile
from app.recommend import recommend
from ingestion.normalize import display_size
from ingestion.scraper import SOURCES, scrape_source

mcp = MCPServer(
    name="BasketIQ",
    instructions=(
        "Azərbaycan supermarketlərinin endirim kataloqlarından qiymət məlumatı. "
        "Səbət müqayisəsi, məhsul axtarışı və kataloq emalı alətləri var. "
        "Qiymətlər manatladır (AZN). Rəqəmləri özündən uydurma - "
        "yalnız alətlərin qaytardığı dəyərləri işlət."
    ),
)


async def _in_thread(func, *args, **kwargs):
    """Sinxron (və uzun) işi ayrıca sapda icra edir ki, server donmasın."""
    return await anyio.to_thread.run_sync(lambda: func(*args, **kwargs))


class ToolError(Exception):
    """Alətin istifadəçiyə göstəriləcək xətası."""


def tool_errors(func):
    """
    HTTPException-ı oxunaqlı mətnə çevirir.

    Niyə? Alətlərimiz FastAPI route funksiyalarını çağırır, onlar isə xətanı
    HTTPException kimi atır. Modelə "HTTPException(404)" yox, "Kataloq tapılmadı"
    getməlidir - model ikincidən nə edəcəyini başa düşür, birincidən yox.
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException as e:
            return f"Xəta: {e.detail}"
        except Exception as e:
            return f"Xəta ({type(e).__name__}): {e}"

    return wrapper


def _size(row: dict) -> str:
    return display_size(row.get("size_value"), row.get("size_unit"))


# ---------------------------------------------------------------- axtarış


@mcp.tool(
    description=(
        "Məhsul adına görə axtarış. Səbətə əlavə etməzdən əvvəl məhsulun id-sini "
        "tapmaq üçün istifadə et. Nümunə sorğu: 'süd', 'düyü', 'dondurma'."
    )
)
@tool_errors
async def search_products(query: str, limit: int = 10) -> str:
    data = await _in_thread(products.search_products, q=query, limit=limit)
    items = data["items"]
    if not items:
        return f"'{query}' üzrə məhsul tapılmadı."

    lines = [f"'{query}' üzrə {len(items)} məhsul:"]
    for row in items:
        brand = f" ({row['brand']})" if row.get("brand") else ""
        lines.append(
            f"  id={row['id']}  {row['name']}{brand} {_size(row)}"
            f"  — {row['store_count']} marketdə"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------- səbət


@mcp.tool(description="Səbətdəki məhsulların siyahısı.")
@tool_errors
async def show_basket() -> str:
    data = await _in_thread(basket.get_basket)
    items = data.get("items", [])
    if not items:
        return "Səbət boşdur."
    lines = [f"Səbətdə {len(items)} məhsul:"]
    for row in items:
        lines.append(f"  id={row['product_id']}  {row['name']}  ×{row['qty']}")
    return "\n".join(lines)


@mcp.tool(
    description=(
        "Səbətə məhsul əlavə edir. product_id-ni əvvəlcə search_products ilə tap. "
        "Məhsulun adını yox, məhz id-sini ver."
    )
)
@tool_errors
async def add_to_basket(product_id: int, qty: float = 1) -> str:
    await _in_thread(basket.add_item, BasketItemIn(product_id=product_id, qty=qty))
    return f"Məhsul #{product_id} səbətə əlavə olundu (miqdar {qty})."


@mcp.tool(description="Səbətdən məhsulu çıxarır.")
@tool_errors
async def remove_from_basket(product_id: int) -> str:
    await _in_thread(basket.remove_item, product_id)
    return f"Məhsul #{product_id} səbətdən çıxarıldı."


@mcp.tool(
    description=(
        "Səbətin hansı marketdə ucuz olduğunu hesablayır. Marketlərin cəmini, "
        "qalibi və qənaəti qaytarır. Səbəti tam əhatə etməyən market qalib "
        "elan edilmir - çatışmayan məhsul cəmi süni şəkildə azaldar."
    )
)
@tool_errors
async def compare_basket() -> str:
    data = await _in_thread(basket.compare)

    if not data["items"]:
        return "Səbət boşdur - müqayisə etmək üçün əvvəlcə məhsul əlavə et."

    lines = [f"Səbətdə {len(data['items'])} məhsul.", "", "Marketlər:"]
    for row in data["stores"]:
        mark = "tam" if row["complete"] else f"natamam ({row['covered']} məhsul)"
        line = f"  {row['store']}: {row['total']:.2f} AZN — {mark}"
        if row.get("diff"):
            line += f"  (+{row['diff']:.2f})"
        lines.append(line)

    if data["best"]:
        lines.append("")
        lines.append(f"Ən ucuz: {data['best']['store']} — {data['best']['total']:.2f} AZN")
        if data["savings"]:
            lines.append(f"Qənaət: {data['savings']:.2f} AZN")
    if data.get("note"):
        lines.append(f"Qeyd: {data['note']}")

    return "\n".join(lines)


@mcp.tool(
    description=(
        "İstifadəçinin profili: ailə ölçüsü, həftəlik büdcə, neçə markete "
        "getməyə hazırdır, istəmədiyi məhsullar. Tövsiyə verməzdən ƏVVƏL bunu "
        "oxu - eyni səbət üçün doğru cavab profildən asılıdır."
    )
)
@tool_errors
async def show_profile() -> str:
    profile = await _in_thread(get_profile)
    return profile.summary()


@mcp.tool(
    description=(
        "Profili dəyişir. Yalnız istifadəçi açıq şəkildə istəyəndə çağır - "
        "məsələn 'biz 4 nəfərik' və ya 'büdcəm 80 manatdır' deyəndə. "
        "Verilməyən sahələr olduğu kimi qalır."
    )
)
@tool_errors
async def update_profile(
    household_size: int | None = None,
    weekly_budget: float | None = None,
    max_stores: int | None = None,
    min_split_saving: float | None = None,
) -> str:
    current = await _in_thread(get_profile)
    updated = Profile(
        household_size=household_size if household_size is not None else current.household_size,
        weekly_budget=weekly_budget if weekly_budget is not None else current.weekly_budget,
        max_stores=max_stores if max_stores is not None else current.max_stores,
        min_split_saving=(
            min_split_saving if min_split_saving is not None else current.min_split_saving
        ),
        prefer_unit_price=current.prefer_unit_price,
        avoid=current.avoid,
    )
    saved = await _in_thread(save_profile, updated)
    return "Profil yeniləndi: " + saved.summary()


@mcp.tool(
    description=(
        "Profilə uyğun konkret alış planı: hansı markete getmək, cəmi neçə "
        "AZN, büdcəyə sığırmı. compare_basket 'hansı market ucuzdur' sualına "
        "cavab verir; bu isə 'MƏNƏ nə etmək sərfəlidir' sualına."
    )
)
@tool_errors
async def recommend_plan() -> str:
    data = await _in_thread(basket.compare)
    rec = (await _in_thread(recommend, data)).as_dict()

    if rec["plan"] == "yoxdur":
        return "\n".join(rec["notes"]) or "Plan qurmaq mümkün olmadı."

    plan_name = "bölünmüş alış" if rec["plan"] == "bolunmus" else "tək market"
    lines = [f"Plan: {plan_name} — {', '.join(rec['stores'])}, cəmi {rec['total']:.2f} AZN"]

    if rec["single_total"] and rec["split_total"]:
        lines.append(
            f"Tək market {rec['single_total']:.2f} AZN, bölünmüş {rec['split_total']:.2f} AZN"
        )
    lines.extend(f"- {note}" for note in rec["notes"])
    lines.extend(f"DİQQƏT: {warn}" for warn in rec["warnings"])

    if rec["plan"] == "bolunmus":
        lines.append("Hansı məhsul harada:")
        for a in rec["assignments"]:
            if a["store"]:
                lines.append(f"  {a['label']} -> {a['store']} ({a['price']} AZN)")
    return "\n".join(lines)


# ---------------------------------------------------------------- kataloqlar


@mcp.tool(description="Scraping üçün mövcud market mənbələri.")
@tool_errors
async def list_sources() -> str:
    lines = ["Mövcud mənbələr:"]
    for source in SOURCES.values():
        lines.append(f"  {source.key} — {source.store}  ({source.page_url})")
    return "\n".join(lines)


@mcp.tool(description="Yüklənmiş kataloqlar: id, market, status.")
@tool_errors
async def list_catalogs(limit: int = 15) -> str:
    rows = await _in_thread(catalogs.list_catalogs)
    if not rows:
        return "Hələ kataloq yüklənməyib."
    lines = [f"{len(rows)} kataloq (son {min(limit, len(rows))}):"]
    for row in rows[:limit]:
        lines.append(
            f"  #{row['id']}  {row['store_name']}  {row['status']}  {row['fetched_at']}"
        )
    return "\n".join(lines)


@mcp.tool(
    description=(
        "Market saytından kataloqu çəkir və mətnini çıxarır. UZUN çəkir: "
        "hər səhifə təxminən 20 saniyə OCR deməkdir, ona görə pages dəyərini "
        "kiçik saxla. Çıxarılan mətndən məhsul yaratmaq üçün sonra "
        "extract_catalog çağır."
    )
)
@tool_errors
async def scrape_catalog(source: str, pages: int = 2) -> str:
    if source not in SOURCES:
        return f"Naməlum mənbə: '{source}'. Mövcud: {', '.join(sorted(SOURCES))}"

    # HTTP route funksiyasını yox, birbaşa scraper-i çağırırıq: route-un API
    # açarı yoxlaması var, MCP serveri isə elə bizim öz prosesimizin içindədir.
    result = await _in_thread(
        scrape_source, key=source, max_files=1, max_pages=pages
    )
    report = result.as_dict()

    lines = [
        f"{report['store']}: {report['found_count']} link tapıldı, "
        f"{len(report['ingested'])} emal olundu, {len(report['skipped'])} ötürüldü."
    ]
    for item in report["ingested"]:
        stats = item.get("stats") or {}
        lines.append(
            f"  kataloq #{item['catalog_id']}  {item['filename']}  "
            f"{stats.get('kept', 0)} məhsul sətri"
        )
    for item in report["skipped"]:
        lines.append(f"  #{item['catalog_id']} ötürüldü — {item['reason']}")
    for err in report["errors"]:
        lines.append(f"  XƏTA: {err}")
    return "\n".join(lines)


@mcp.tool(
    description=(
        "Kataloqun sətirlərini AI ilə struktur məhsullara çevirir və bazaya yazır. "
        "Hər sətir təxminən 10 saniyə çəkir - limit dəyərini kiçik saxla."
    )
)
@tool_errors
async def extract_catalog(catalog_id: int, limit: int = 10) -> str:
    result = await _in_thread(
        catalogs.extract_catalog_endpoint, catalog_id=catalog_id, limit=limit
    )
    lines = [
        f"Kataloq #{catalog_id} ({result['store']}): "
        f"{result['processed']} sətir emal olundu, "
        f"{result['saved']} məhsul yazıldı, {result['skipped']} ötürüldü."
    ]
    for product in result["products"][:10]:
        lines.append(f"  {product['name']} — {product['price']} AZN")
    return "\n".join(lines)


# ---------------------------------------------------------------- sistem


@mcp.tool(description="Sistem statusu: baza sayğacları və Ollama əlçatanlığı.")
@tool_errors
async def health() -> str:
    db = await _in_thread(db_stats)
    llm = await _in_thread(check_llm)
    return (
        f"Baza: {db['stores']} market, {db['catalogs']} kataloq, "
        f"{db['products']} məhsul, {db['prices']} qiymət.\n"
        f"Ollama: {'işləyir' if llm.get('reachable') else 'əlçatmazdır'} "
        f"({llm.get('model', '?')})"
    )


# ---------------------------------------------------------------- işə salma


def http_app(path: str = "/"):
    """
    FastAPI-yə qoşmaq üçün ASGI tətbiqi.

    path="/" qoyulur, çünki tətbiq `/mcp` altına mount olunur - daxildə yenidən
    `/mcp` yazsaq, ünvan `/mcp/mcp` olardı.
    """
    return mcp.streamable_http_app(streamable_http_path=path, stateless_http=True)


def main() -> None:
    import sys

    if "--http" in sys.argv:
        # Ayrıca proses kimi (FastAPI-dən asılı olmadan sınamaq üçün)
        mcp.run(transport="streamable-http", host="127.0.0.1", port=8765)
    else:
        # stdio - Claude Desktop və digər lokal MCP klientləri belə qoşulur
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
