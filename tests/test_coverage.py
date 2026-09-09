"""
NATAMAM ƏHATƏ (D15/D16/D17) — boş market saytı sındırmamalıdır.

BURADAKI ƏSAS RİSK BİR CÜMLƏYLƏ: datası olmayan marketin cəmi 0.00-dır.
Hesablama onu adi market kimi saysaydı, «ən ucuz market» həmişə BOŞ market
olardı - səhifə işləyər, rəqəm görünər, cavab isə tamamilə yanlış olardı.

İkinci risk daha sakitdir: boş marketi sütunlardan silmək. Səhifə onda düzgün
işləyir, sadəcə istifadəçiyə vəd olunan dörd marketin ikisi yox olur və səbəb
heç yerdə yazılmır.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.coverage import store_coverage
from app.db import db_cursor
from app.main import app
from app.stores import MARKETS

client = TestClient(app)


@pytest.fixture
def səbət():
    """
    Səbətə iki məhsul qoyur: biri İKİ markette, biri yalnız BİRİNDƏ.

    Belə qurulub ki, «tam əhatə» məntiqi də sınansın: natamam market qalib
    seçilə bilməz.
    """
    araz = _market("araz", "Araz")
    bravo = _market("bravo", "Bravo")

    hər_ikisi = _məhsul("ehate|her-ikisi")
    tək = _məhsul("ehate|tek")

    _qiymət(hər_ikisi, araz, 2.00)
    _qiymət(hər_ikisi, bravo, 3.00)
    _qiymət(tək, araz, 5.00)

    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE basket_id = 1")
        for pid in (hər_ikisi, tək):
            cur.execute(
                "INSERT INTO basket_items (basket_id, product_id, qty) VALUES (1, ?, 1)",
                (pid,),
            )
    yield
    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE basket_id = 1")


def _market(slug: str, name: str) -> int:
    with db_cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO stores (slug, name) VALUES (?, ?)", (slug, name))
        return cur.lastrowid


def _məhsul(key: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key) VALUES (?, ?, ?)",
            (f"{key}|{uuid.uuid4().hex[:6]}", "əhatə məhsulu", key),
        )
        return cur.lastrowid


def _qiymət(product_id: int, store_id: int, price: float) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, status) "
            "VALUES (?, ?, 'coverage-test.pdf', 'parsed')",
            (store_id, uuid.uuid4().hex),
        )
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price, seen_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (product_id, store_id, cur.lastrowid, price),
        )


# ------------------------------------------------- müqayisə cədvəli (D17)


def test_dörd_sütunun_hamısı_qalır(səbət):
    """
    İstifadəçiyə DÖRD market vəd olunub. Datası olmayanı sütunlardan silsək,
    o, saytın «yalnız iki marketi bilməsi» kimi oxunar - halbuki səbəb
    kataloqun hələ gəlməməsidir.
    """
    data = client.get("/api/basket/compare").json()
    slugs = [s["slug"] for s in data["stores"]]
    assert set(slugs) == {m.slug for m in MARKETS}, "sütunlar reyestrlə üst-üstə düşmür"

    # DATASIZ MARKET SONDA. Sıralama cəmə görədir və boş marketin cəmi
    # 0.00-dır - yəni süzgəc olmasa, boş sütun dolu sütunu qabaqlayardı.
    hazır = [s["available"] for s in data["stores"]]
    assert hazır == sorted(hazır, reverse=True), "datasız market dolu marketdən əvvəl gəlir"


def test_datasız_market_açıq_nişanlanır(səbət):
    """UI «tezliklə» yazısını məhz bu sahədən oxuyur."""
    stores = {s["slug"]: s for s in client.get("/api/basket/compare").json()["stores"]}
    assert stores["araz"]["available"] is True
    assert stores["bazar-store"]["available"] is False
    assert stores["rahat"]["available"] is False


def test_iki_datasız_market_bir_birini_əvəz_etmir(səbət):
    """
    Bazar Store və Rahat üçün `stores` cədvəlində sətir YOXDUR, yəni hər
    ikisinin id-si `None`-dur. Daxili açar id olsaydı, ikisi eyni xanaya
    düşüb biri yox olardı - cədvəldə üç sütun qalardı.
    """
    stores = client.get("/api/basket/compare").json()["stores"]
    id_siz = [s for s in stores if s["store_id"] is None]
    assert len(id_siz) == 2
    assert {s["slug"] for s in id_siz} == {"bazar-store", "rahat"}


# ------------------------------------------------ hesablamanın toxunulmazlığı


def test_boş_market_ən_ucuz_seçilmir(səbət):
    """
    ƏSAS RİSK. Boş marketin cəmi 0.00-dır və sıralama cəmə görədir.
    «Tam əhatə» şərti olmasaydı, qalib həmişə boş market olardı.
    """
    data = client.get("/api/basket/compare").json()
    assert data["best"] is not None
    assert data["best"]["available"] is True
    assert data["best"]["total"] > 0


def test_boş_market_tam_əhatəli_sayılmır(səbət):
    data = client.get("/api/basket/compare").json()
    for store in data["stores"]:
        if not store["available"]:
            assert store["complete"] is False
            assert store["covered"] == 0


def test_ən_ucuz_mümkün_cəm_boş_marketdən_təsirlənmir(səbət):
    """
    2.00 (Araz) + 5.00 (Araz) = 7.00. Boş market xanaları «0» sayılsaydı,
    rəqəm aşağı düşərdi və istifadəçi mövcud olmayan qənaətə inanardı.
    """
    data = client.get("/api/basket/compare").json()
    assert data["cheapest"]["total"] == pytest.approx(7.00)
    assert data["cheapest"]["unavailable"] == 0


# ------------------------------------------------------ əhatə cədvəli (D15)


def test_əhatə_cədvəlində_dörd_market_var():
    nəticə = store_coverage()
    assert {i["slug"] for i in nəticə["items"]} == {m.slug for m in MARKETS}


def test_boş_marketin_son_yenilənməsi_yoxdur():
    """
    `None` qəsdəndir: uydurma tarix («bu gün») marketin data aldığı
    təəssüratını yaradardı. UI onu «heç vaxt» kimi yazır.
    """
    sətirlər = {i["slug"]: i for i in store_coverage()["items"]}
    assert sətirlər["rahat"]["last_seen"] is None
    assert sətirlər["rahat"]["products"] == 0
    assert sətirlər["rahat"]["coverage_pct"] == 0


def test_əhatə_faizi_0_100_aralığındadır():
    for sətir in store_coverage()["items"]:
        assert 0 <= sətir["coverage_pct"] <= 100


def test_hər_sətir_mənbə_vəziyyətini_daşıyır():
    """«Niyə boşdur?» sualının cavabı elə həmin sətirdə olmalıdır."""
    for sətir in store_coverage()["items"]:
        assert sətir["source_status"] in {"active", "manual", "blocked"}
        assert sətir["source_note"]


def test_dolu_market_cədvəlin_başındadır():
    hazır = [i["available"] for i in store_coverage()["items"]]
    assert hazır == sorted(hazır, reverse=True)


def test_əhatə_endpoint_i_qapının_arxasındadır():
    """
    Bu cədvəl saytın DAXİLİ vəziyyətidir: hansı mənbə bağlıdır, data nə
    qədər boşdur. İstifadəçiyə lazım deyil, rəqibə isə lazım ola bilər.
    """
    from app.config import settings

    əvvəlki = settings.admin_enabled
    settings.admin_enabled = False
    try:
        assert client.get("/api/admin/coverage").status_code == 404
    finally:
        settings.admin_enabled = əvvəlki
