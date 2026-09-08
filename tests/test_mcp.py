"""
MCP serveri testləri.

Şəbəkə qaldırmırıq: MCP SDK-nın `Client`-i serverə PROSESDAXİLİ qoşula bilir.
Beləliklə eyni testlər həm lokalda, həm CI-da işləyir və port münaqişəsi olmur.

Testlərin əsas sualı: alətlərin TƏSVİRİ modelin onları düzgün seçməsi üçün
kifayətdirmi, cavablar isə qısa və oxunaqlıdırmı? MCP-də alətin təsviri kod
qədər vacibdir - model yalnız onu görür.
"""

import pytest
from mcp.client import Client

from app.db import db_cursor, get_connection
from mcp_server.server import mcp

GOZLENILEN_ALETLER = {
    "search_products",
    "show_basket",
    "add_to_basket",
    "remove_from_basket",
    "compare_basket",
    "list_sources",
    "list_catalogs",
    "scrape_catalog",
    "extract_catalog",
    "health",
}


async def _tools():
    async with Client(mcp) as client:
        result = await client.list_tools()
    return result.tools if hasattr(result, "tools") else result


async def _call(name: str, args: dict | None = None) -> str:
    async with Client(mcp) as client:
        result = await client.call_tool(name, args or {})
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


# ------------------------------------------------------------------ alət təsviri


async def test_butun_aletler_qeydiyyatdadir():
    names = {tool.name for tool in await _tools()}
    assert GOZLENILEN_ALETLER <= names, f"Çatışmayan alət: {GOZLENILEN_ALETLER - names}"


async def test_her_aletin_izahi_var():
    """Təsvirsiz alət modelin gözündə görünməzdir - onu heç vaxt çağırmaz."""
    for tool in await _tools():
        assert tool.description, f"'{tool.name}' alətinin təsviri yoxdur"
        assert len(tool.description) > 20, f"'{tool.name}' təsviri çox qısadır"


async def test_parametrlerin_sxemi_duzgundur():
    tools = {tool.name: tool for tool in await _tools()}

    schema = tools["add_to_basket"].input_schema
    assert "product_id" in schema["properties"]
    assert schema["properties"]["product_id"]["type"] == "integer"
    # qty defoltludur -> məcburi deyil
    assert schema.get("required") == ["product_id"]

    schema = tools["search_products"].input_schema
    assert schema["properties"]["query"]["type"] == "string"


# ------------------------------------------------------------------ cavablar


async def test_health_bazani_ve_modeli_bildirir():
    text = await _call("health")
    assert "Baza:" in text
    assert "kataloq" in text
    assert "Ollama:" in text


async def test_menbe_siyahisi():
    text = await _call("list_sources")
    assert "araz" in text
    assert "kenar-market" not in text


async def test_tapilmayan_mehsul_aydin_cavab_verir():
    text = await _call("search_products", {"query": "beləməhsulyoxdur", "limit": 5})
    assert "tapılmadı" in text


async def test_nameluм_menbe_xeta_atmir_izah_edir():
    """
    Alət exception atmamalıdır - model onu oxuya bilmir.

    Modelə "belə mənbə yoxdur, mövcudlar bunlardır" desək, o, özü düzəldir.
    """
    text = await _call("scrape_catalog", {"source": "yoxdur", "pages": 1})
    assert "Naməlum mənbə" in text
    assert "araz" in text


async def test_olmayan_kataloq_xetani_metne_cevirir():
    text = await _call("extract_catalog", {"catalog_id": 999999, "limit": 1})
    assert "Xəta" in text
    assert "tapılmadı" in text


# ------------------------------------------------------------------ səbət axını


@pytest.fixture
def temiz_sebet():
    """Testdən sonra səbəti əvvəlki halına qaytarır."""
    conn = get_connection()
    before = [
        dict(r)
        for r in conn.execute(
            "SELECT product_id, qty FROM basket_items WHERE basket_id = 1"
        ).fetchall()
    ]
    product = conn.execute("SELECT id FROM products LIMIT 1").fetchone()
    conn.close()
    if product is None:
        pytest.skip("Bazada məhsul yoxdur - səbət testi ötürülür")

    yield product["id"]

    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE basket_id = 1")
        for row in before:
            cur.execute(
                "INSERT INTO basket_items (basket_id, product_id, qty) VALUES (1, ?, ?)",
                (row["product_id"], row["qty"]),
            )


async def test_sebete_elave_et_ve_cixar(temiz_sebet):
    product_id = temiz_sebet

    text = await _call("add_to_basket", {"product_id": product_id, "qty": 2})
    assert str(product_id) in text

    text = await _call("show_basket")
    assert f"id={product_id}" in text

    text = await _call("remove_from_basket", {"product_id": product_id})
    assert str(product_id) in text


async def test_olmayan_mehsulu_sebete_elave_etmek(temiz_sebet):
    text = await _call("add_to_basket", {"product_id": 999999})
    assert "Xəta" in text


async def test_muqayise_cavabi_qisadir(temiz_sebet):
    """
    Cavabın hər simvolu modelin konteksinə düşür.

    `compare()` funksiyasının xam JSON-u minlərlə simvoldur; alət isə yalnız
    qərar üçün lazım olanı verməlidir.
    """
    await _call("add_to_basket", {"product_id": temiz_sebet})
    text = await _call("compare_basket")
    assert len(text) < 1500, f"Cavab çox uzundur: {len(text)} simvol"
    assert "Marketlər:" in text or "Səbət boşdur" in text
