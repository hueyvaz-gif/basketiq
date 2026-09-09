"""
Səbət və market müqayisəsi — layihənin istifadəçiyə görünən əsas dəyəri.

MÜHÜM DETAL: müqayisə product_id üzərində YOX, group_key üzərində aparılır.
Çünki "Süd Milla 1 L" Bravo-da bir product_id, Araz-da başqa product_id-dir.
Matching onları eyni group_key altında birləşdirib - müqayisə də ona görə
qrupla işləyir.

İKİNCİ MÜHÜM DETAL: bir market səbətdəki məhsulun 3-ünü satmırsa, onun cəmi
avtomatik olaraq "ucuz" görünür. Ona görə hər market üçün ƏHATƏ (coverage)
ayrıca göstərilir və natamam marketlər "ən ucuz" elan edilmir.
"""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai.advisor import build_facts, stream_advice, verify_numbers
from ai.sanitize import strip_reasoning

from app.db import db_cursor, get_connection
from app.profile import get_profile
from app.stores import MARKETS, display_names
from ingestion.normalize import display_label, display_size

router = APIRouter(prefix="/api/basket", tags=["basket"])

DEFAULT_BASKET_ID = 1


class BasketItemIn(BaseModel):
    product_id: int
    qty: float = 1.0


def _ensure_basket(basket_id: int) -> None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM baskets WHERE id = ?", (basket_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Səbət tapılmadı")


# ------------------------------------------------------------------ səbət CRUD


@router.get("")
def get_basket(basket_id: int = DEFAULT_BASKET_ID):
    _ensure_basket(basket_id)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT bi.product_id, bi.qty, p.name, p.brand, p.size_value, p.size_unit, "
            "       p.category, p.group_key "
            "FROM basket_items bi JOIN products p ON p.id = bi.product_id "
            "WHERE bi.basket_id = ? ORDER BY bi.id",
            (basket_id,),
        ).fetchall()
        return {"basket_id": basket_id, "items": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("/items")
def add_item(item: BasketItemIn, basket_id: int = DEFAULT_BASKET_ID):
    _ensure_basket(basket_id)
    conn = get_connection()
    try:
        exists = conn.execute("SELECT id FROM products WHERE id = ?", (item.product_id,)).fetchone()
    finally:
        conn.close()
    if not exists:
        raise HTTPException(404, "Məhsul tapılmadı")

    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO basket_items (basket_id, product_id, qty) VALUES (?, ?, ?) "
            "ON CONFLICT(basket_id, product_id) DO UPDATE SET qty = excluded.qty",
            (basket_id, item.product_id, item.qty),
        )
    return {"added": item.product_id, "qty": item.qty}


@router.delete("/items/{product_id}")
def remove_item(product_id: int, basket_id: int = DEFAULT_BASKET_ID):
    with db_cursor() as cur:
        cur.execute(
            "DELETE FROM basket_items WHERE basket_id = ? AND product_id = ?",
            (basket_id, product_id),
        )
    return {"removed": product_id}


# ------------------------------------------------------------------ müqayisə


def _latest_prices_by_group(group_keys: list[str]) -> dict:
    """
    Hər (qrup, market) üçün ƏN SON qiyməti gətirir.

    Niyə ən son? Kataloqlar həftəlik yenilənir; köhnə qiymətlə müqayisə
    aparmaq istifadəçini yanıldardı. Tarixçə isə trend üçün DB-də qalır.
    """
    if not group_keys:
        return {}

    placeholders = ",".join("?" * len(group_keys))
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT p.group_key, s.id AS store_id, s.name AS store_name,
                   pr.price, pr.unit_price, pr.raw_line, pr.seen_at,
                   p.name, p.brand
            FROM prices pr
            JOIN products p ON p.id = pr.product_id
            JOIN stores  s ON s.id = pr.store_id
            WHERE p.group_key IN ({placeholders})
              AND pr.id = (
                  SELECT pr2.id FROM prices pr2
                  JOIN products p2 ON p2.id = pr2.product_id
                  WHERE p2.group_key = p.group_key AND pr2.store_id = pr.store_id
                  ORDER BY pr2.seen_at DESC, pr2.id DESC LIMIT 1
              )
            """,
            group_keys,
        ).fetchall()
        return {(r["group_key"], r["store_id"]): dict(r) for r in rows}
    finally:
        conn.close()


def _all_stores() -> list[dict]:
    """
    Müqayisədə iştirak edən marketlər — YALNIZ bizim dördümüz.

    ƏVVƏL BÜTÜN BAZA GƏLİRDİ və bu, ekranda görünürdü: səbət cavabı
    kənar marketi «ən çox əhatə» kimi göstərirdi, halbuki o, bizim marketimiz deyil və ana
    səhifədəki market şəbəkəsində ümumiyyətlə yoxdur. İstifadəçi ona vəd
    edilməyən, üstəlik başqa yerdə göstərilməyən marketə yönləndirilirdi.

    Ad da reyestrdən götürülür (`Araz` yox, `Araz Market`): bazadakı sərbəst
    yazılmış ad ilə məhsulun adı fərqli olsa, eyni market iki cür görünür və
    market rəngi də (`store-colors.js` onu ADDAN hesablayır) səhifədən
    səhifəyə dəyişir.

    Admin panelinə TOXUNULMUR: orada kataloq və mənbə siyahısı bazanın bütün
    tarixçəsini göstərməkdə haqlıdır - o, məhsulun içidir, cavabı deyil.
    """
    conn = get_connection()
    try:
        names = display_names(conn)
        if not names:
            return []
        rows = conn.execute(
            "SELECT DISTINCT s.id FROM stores s JOIN prices pr ON pr.store_id = s.id"
        ).fetchall()
        stores = [
            {"id": row["id"], "name": names[row["id"]]}
            for row in rows
            if row["id"] in names
        ]
        # Sıra REYESTRDƏKİ sıradır, əlifba deyil: marketlər hər səhifədə eyni
        # ardıcıllıqla görünsün.
        order = {market.name: i for i, market in enumerate(MARKETS)}
        stores.sort(key=lambda s: order.get(s["name"], len(order)))
        return stores
    finally:
        conn.close()


@router.get("/compare")
def compare(basket_id: int = DEFAULT_BASKET_ID):
    """Səbəti bütün marketlərdə müqayisə edir."""
    basket = get_basket(basket_id)
    items = basket["items"]
    if not items:
        return {"basket_id": basket_id, "items": [], "stores": [], "best": None}

    stores = _all_stores()
    price_map = _latest_prices_by_group([i["group_key"] for i in items])

    # Uyğunluq etibarı BİR sorğuda hesablanır - hər sətir üçün ayrıca sorğu
    # N+1 vərdişini gətirərdi.
    from app.catalog import match_confidence
    from app.db import get_connection as _conn

    _c = _conn()
    try:
        confidence = match_confidence(_c, [i["group_key"] for i in items])
    finally:
        _c.close()

    item_rows = []
    store_totals = {s["id"]: {"store_id": s["id"], "store": s["name"], "total": 0.0,
                              "covered": 0, "missing": [], "cheapest_count": 0}
                    for s in stores}

    for item in items:
        label = display_label(item["name"], item.get("brand"))
        prices: dict[int, dict] = {}

        for store in stores:
            found = price_map.get((item["group_key"], store["id"]))
            if found:
                prices[store["id"]] = {
                    "price": found["price"],
                    "unit_price": found["unit_price"],
                    "raw_line": found["raw_line"],
                }

        cheapest_store = None
        if prices:
            cheapest_store = min(prices, key=lambda sid: prices[sid]["price"])

        for store in stores:
            entry = store_totals[store["id"]]
            found = prices.get(store["id"])
            if found:
                entry["total"] += found["price"] * item["qty"]
                entry["covered"] += 1
                if store["id"] == cheapest_store:
                    entry["cheapest_count"] += 1
            else:
                entry["missing"].append(label)

        item_rows.append({
            "product_id": item["product_id"],
            "label": label,
            # Kateqoriya UI-da ikon seçmək üçündür: "süd məhsulları" -> şüşə ikonu.
            # Yeni data DEYİL - `products.category` sütununda onsuz da var idi,
            # sadəcə müqayisə cavabına daxil edilməmişdi.
            "category": item.get("category") or "digər",
            "size": display_size(item.get("size_value"), item.get("size_unit")),
            "qty": item["qty"],
            "prices": {str(sid): value for sid, value in prices.items()},
            "cheapest_store_id": cheapest_store,
            "available_in": len(prices),
            # A4: marketlərarası uyğunluq dəqiqdir, yoxsa təxmini?
            "match": confidence.get(item["group_key"], "exact"),
            # D18: neçə marketdə var / dörd marketdən
            "coverage": {"available": len(prices), "total": len(MARKETS)},
        })

    results = []
    for entry in store_totals.values():
        entry["total"] = round(entry["total"], 2)
        entry["complete"] = entry["covered"] == len(items)
        results.append(entry)

    # Yalnız SƏBƏTİ TAM ƏHATƏ EDƏN marketlər "ən ucuz" ola bilər.
    # Natamam market ucuz görünür, çünki çatışmayan məhsul 0 sayılır.
    complete = [r for r in results if r["complete"]]
    best = min(complete, key=lambda r: r["total"]) if complete else None

    if best:
        for entry in results:
            entry["diff"] = round(entry["total"] - best["total"], 2) if entry["complete"] else None

    results.sort(key=lambda r: (not r["complete"], r["total"]))

    savings = None
    if best and len(complete) > 1:
        worst = max(complete, key=lambda r: r["total"])
        savings = round(worst["total"] - best["total"], 2)

    # ƏLDƏ EDİLƏ BİLƏN ƏN UCUZ CƏM: hər məhsulu ən ucuz satan marketdən alsan.
    #
    # NİYƏ LAZIMDIR? Marketlərin assortimenti fərqli olanda heç biri səbətin
    # hamısını satmır və `best` boş qalır - yəni istifadəçi ekranda HEÇ BİR
    # rəqəm görmür. Halbuki onun sualının cavabı var: "bu səbət ən azı neçəyə
    # başa gəlir?" Bu rəqəm həmin cavabdır.
    #
    # Bu, `best`-i ƏVƏZ ETMİR: tək marketdən alış həmişə üstündür (yol, vaxt).
    # Ona görə qalib varsa, hero yenə onu göstərir; bu rəqəm yalnız qalib
    # olmayanda işə düşür.
    cheapest_total = 0.0
    cheapest_stores: set[int] = set()
    unavailable = 0

    for row in item_rows:
        prices = row["prices"]
        if not prices:
            unavailable += 1
            continue
        store_id = row["cheapest_store_id"]
        cheapest_total += prices[str(store_id)]["price"] * row["qty"]
        cheapest_stores.add(store_id)

    cheapest = {
        "total": round(cheapest_total, 2),
        "store_count": len(cheapest_stores),
        # Səbətdə heç bir marketdə tapılmayan məhsul varsa, cəm NATAMAMDIR -
        # istifadəçi bunu bilməlidir, yoxsa rəqəmə tam etibar edər.
        "unavailable": unavailable,
    } if item_rows else None

    return {
        "basket_id": basket_id,
        "items": item_rows,
        "stores": results,
        "best": best,
        "savings": savings,
        "cheapest": cheapest,
        "note": None if complete else "Heç bir market səbətin hamısını satmır - "
                                      "cəmlər natamam olduğu üçün müqayisə edilmir.",
    }


@router.get("/advise")
async def advise(basket_id: int = DEFAULT_BASKET_ID):
    """
    AI tövsiyəsini Server-Sent Events (SSE) ilə token-token göndərir.

    Niyə SSE, adi JSON deyil? Cavab ~22 saniyə yazılır. Adi endpoint bütün
    mətn hazır olana qədər susardı. SSE ilə brauzer ilk sözü 2-3 saniyəyə alır.

    Niyə WebSocket deyil? Axın tək istiqamətlidir (server -> brauzer).
    SSE bunun üçün kifayətdir və adi HTTP üzərində işləyir - əlavə
    infrastruktur, xüsusi proxy konfiqurasiyası tələb etmir.
    """
    data = compare(basket_id=basket_id)

    if not data["items"]:
        async def empty():
            yield _sse({"type": "error", "text": "Səbət boşdur."})
        return StreamingResponse(empty(), media_type="text/event-stream")

    # Profil faktlara qoşulur: model rəqəmləri dəyişmir, amma tövsiyəni
    # istifadəçinin şəraitinə uyğunlaşdırır (tək markete gedən adama
    # "iki marketi gəz" deməsin).
    summary = get_profile().summary()
    facts = build_facts(data, summary)

    async def generate():
        collected: list[str] = []
        try:
            async for chunk in stream_advice(data, summary):
                collected.append(chunk)
                yield _sse({"type": "token", "text": chunk})
        except Exception as e:
            yield _sse({"type": "error", "text": f"{type(e).__name__}: {e}"})
            return

        # Axın bitdi. İndi TAM mətni bir daha təmizləyirik.
        #
        # Niyə ikinci dəfə? Axın filtri yalnız etiketli blokları tuta bilir -
        # o, mətni hissə-hissə görür. "Cavab:" kimi son-cavab markeri isə
        # yalnız TAM mətndə mənalıdır: ondan əvvəlki hər şey düşüncədir, amma
        # bunu ancaq marker gələndə bilirik - o vaxta qədər mətn artıq
        # ekrandadır. Ona görə son versiyanı `done` ilə göndəririk və UI
        # mətni onunla əvəz edir (dəyişməyibsə heç nə görünmür).
        final_text = strip_reasoning("".join(collected))

        # Rəqəm yoxlaması TƏMİZ mətn üzərində aparılır: düşüncə blokundakı
        # aralıq rəqəmlər saxta xəbərdarlıq yaratmasın.
        yield _sse({
            "type": "done",
            "text": final_text,
            "check": verify_numbers(final_text, facts),
        })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Nginx-in cavabı buferləməsinin qarşısını alır - production-da
            # bu olmasa streaming işləmir və mətn birdəfəyə gəlir.
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/facts")
def facts(basket_id: int = DEFAULT_BASKET_ID):
    """Modelə göndərilən faktlar - "AI bunu haradan bildi?" sualına cavab."""
    return {"facts": build_facts(compare(basket_id=basket_id), get_profile().summary())}


def _sse(payload: dict) -> str:
    """SSE formatı: 'data: <json>' və ardınca BOŞ sətir (iki \n)."""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
