"""
SƏBƏT SƏHİFƏSİ VƏ PLANIN MƏZMUNU (P1).

Səbət layihənin ƏSAS vədidir: «bu səbət harada ucuzdur?». Vəd yalnız o zaman
ödənir ki, istifadəçi (a) məhsulu bir kliklə səbətə ata bilsin, (b) səbəti
istənilən səhifədən aça bilsin, (c) planın MƏZMUNUNU görsün - hansı məhsulu
haradan almalı.

BU TESTLƏRİN TUTDUĞU SƏHV: plan başlığı və cəmi görünür, məzmunu isə boşdur.
Səhifə «işləyir», rəqəm də var - amma tövsiyə yoxlana bilmir. Məhz bu hal
canlı yoxlamada üzə çıxdı: `assignments` yalnız BÖLÜNMÜŞ planda doldurulurdu.
"""

import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.basket import compare
from app.db import db_cursor
from app.main import app
from app.profile import get_profile
from app.recommend import recommend

client = TestClient(app)
STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def _market(slug: str, name: str) -> int:
    with db_cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO stores (slug, name) VALUES (?, ?)", (slug, name))
        return cur.lastrowid


def _məhsul(key: str, ad: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key, category) "
            "VALUES (?, ?, ?, 'süd məhsulları')",
            (f"{key}|{uuid.uuid4().hex[:6]}", ad, key),
        )
        return cur.lastrowid


def _qiymət(product_id: int, store_id: int, price: float) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, status) "
            "VALUES (?, ?, 'basket-test.pdf', 'parsed')",
            (store_id, uuid.uuid4().hex),
        )
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price, seen_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (product_id, store_id, cur.lastrowid, price),
        )


@pytest.fixture
def səbət():
    """İki məhsul, hər ikisi İKİ marketdə - tək market planı seçilə bilir."""
    araz = _market("araz", "Araz")
    bravo = _market("bravo", "Bravo")

    a = _məhsul("sebet|bir", "birinci məhsul")
    b = _məhsul("sebet|iki", "ikinci məhsul")
    _qiymət(a, araz, 2.00)
    _qiymət(a, bravo, 2.50)
    _qiymət(b, araz, 5.00)
    _qiymət(b, bravo, 5.50)

    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE basket_id = 1")
        for pid in (a, b):
            cur.execute(
                "INSERT INTO basket_items (basket_id, product_id, qty) VALUES (1, ?, 1)",
                (pid,),
            )
    yield {"a": a, "b": b, "araz": araz, "bravo": bravo}
    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE basket_id = 1")


# ------------------------------------------------------------------ səhifə


def test_səbət_səhifəsi_açılır():
    res = client.get("/basket")
    assert res.status_code == 200
    assert "basket-page.js" in res.text


def test_səbət_nişanı_hər_səhifədədir():
    """
    Nişan istifadəçinin səbətə YEGANƏ yoludur. Bir səhifədə unudulsa,
    istifadəçi oradan çıxa bilmir - səhv isə yalnız həmin səhifədə görünür.
    """
    for yol in ("/", "/basket", "/search", "/product/1", "/store/araz"):
        html = client.get(yol).text
        assert "data-basket-count" in html, f"{yol} səhifəsində səbət nişanı yoxdur"
        assert 'href="/basket"' in html, f"{yol} səhifəsi səbətə keçid vermir"


def test_səbətə_əlavə_düyməsi_kartlarda_var():
    """
    Düymə `ui.js`-dəki ORTAQ funksiyadan gəlir. Kart öz düyməsini əl ilə
    yazsaydı, biri `qty` göndərməyi unudardı və səhv yalnız səbətdə görünərdi.
    """
    ui = (STATIC / "ui.js").read_text(encoding="utf-8")
    assert "function addToBasket" in ui
    assert "const addButton" in ui

    for fayl in ("search.js", "product.js"):
        mətn = (STATIC / fayl).read_text(encoding="utf-8")
        assert "addButton(" in mətn, f"{fayl} səbətə əlavə düyməsi çəkmir"


def test_kart_keçidin_içində_düymə_saxlamır():
    """
    HTML qaydası: `<a>` içində `<button>` olmaz - brauzer elementi ya keçid,
    ya düymə kimi oxuyur və klaviatura naviqasiyası pozulur. Kart indi
    `<div>`-dir, içində keçid və düymə AYRI dayanır.
    """
    for fayl in ("search.js", "product.js"):
        mətn = (STATIC / fayl).read_text(encoding="utf-8")
        assert '<a class="pcard"' not in mətn, f"{fayl}: kart hələ də keçiddir"
        assert '<a class="pcard-link"' in mətn, f"{fayl}: kart keçidi tapılmadı"


# ------------------------------------------------------------ planın məzmunu


def test_tək_market_planının_məzmunu_var(səbət):
    """
    ƏSAS TEST. Əvvəl `assignments` yalnız bölünmüş planda doldurulurdu -
    tək market tövsiyə olunanda səhifədə başlıq və cəm görünür, MƏZMUN isə
    boş qalırdı. İstifadəçi «hansı məhsul neçəyədir?» sualının cavabını
    tapa bilmirdi, halbuki rəqəmlər onsuz da hesablanmışdı.
    """
    profil = get_profile()
    plan = recommend(compare(basket_id=1), profil).as_dict()

    assert plan["plan"] in {"tek_market", "bolunmus"}
    assert len(plan["assignments"]) == 2, "planın məzmunu boşdur"
    for sətir in plan["assignments"]:
        assert sətir["store"], "məhsul heç bir markete təyin olunmayıb"
        assert sətir["price"] is not None


def test_plan_səbətdən_qidalanır(səbət):
    """Səbətdən məhsul silinəndə plan da dəyişməlidir - əks halda iki həqiqət olur."""
    əvvəl = recommend(compare(basket_id=1)).as_dict()
    assert len(əvvəl["assignments"]) == 2

    client.delete(f"/api/basket/items/{səbət['b']}")

    sonra = recommend(compare(basket_id=1)).as_dict()
    assert len(sonra["assignments"]) == 1
    assert sonra["total"] < əvvəl["total"]


def test_qiyməti_olmayan_məhsul_planı_pozmur(səbət):
    """
    Heç bir marketdə qiyməti olmayan məhsul plandan ATILMIR: sətri qalır,
    marketi `None` olur və UI «heç bir marketdə qiyməti yoxdur» yazır.
    Atılsaydı, istifadəçi onu aldığını sanardı; cəmə qatılsaydı, rəqəm
    yalan olardı.
    """
    yetim = _məhsul("sebet|qiymetsiz", "qiyməti olmayan məhsul")
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO basket_items (basket_id, product_id, qty) VALUES (1, ?, 1)",
            (yetim,),
        )

    data = compare(basket_id=1)
    plan = recommend(data).as_dict()

    qiymətsiz = [a for a in plan["assignments"] if a["store"] is None]
    assert len(qiymətsiz) == 1
    assert qiymətsiz[0]["price"] is None
    # Cəm yalnız qiyməti olan məhsullardan ibarətdir.
    assert plan["total"] == pytest.approx(7.00)
    assert data["cheapest"]["unavailable"] == 1


def test_datasız_market_səbət_səhifəsində_açıq_yazılır(səbət):
    """
    «Bu marketdə qiymət yoxdur» ilə «bahalıdır» fərqlənməlidir: boş marketin
    cəmi 0.00-dır və gizlədilsə, istifadəçi onu ucuz sanardı.
    """
    stores = {s["slug"]: s for s in compare(basket_id=1)["stores"]}
    assert stores["bazar-store"]["available"] is False
    assert stores["rahat"]["available"] is False

    js = (STATIC / "basket-page.js").read_text(encoding="utf-8")
    assert "basket.noData" in js, "səbət səhifəsi datasız marketi izah etmir"


def test_miqdar_dəyişikliyi_cəmi_dəyişir(səbət):
    """«+» düyməsi qiyməti qat-qat artırmalıdır - yoxsa miqdar bəzəkdir."""
    bir = recommend(compare(basket_id=1)).as_dict()["total"]

    client.post("/api/basket/items", json={"product_id": səbət["a"], "qty": 3})

    üç = recommend(compare(basket_id=1)).as_dict()["total"]
    assert üç == pytest.approx(bir + 2 * 2.00)


# ------------------------------------------------------------------ skelet (P2)


def test_səhifələr_boş_ekran_göstərmir():
    """
    P2: yüklənmə anında ağ ekran olmamalıdır. Hər dinamik qutu ilk
    render-də ya skelet, ya da mətn saxlamalıdır - `innerHTML` boş
    başlasaydı, data gələnə qədər səhifədə ağ boşluq qalardı.
    """
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    assert ".skeleton-row" in css, "skelet üslubu yoxdur"

    for səhifə in ("index.html", "basket.html", "product.html", "search.html"):
        html = (STATIC / səhifə).read_text(encoding="utf-8")
        assert "skeleton" in html, f"{səhifə} ilk render-də skelet göstərmir"


def test_skelet_hərəkəti_söndürülə_bilir():
    """`prefers-reduced-motion` qaydası: parıltı dayanır, forma qalır."""
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    blok = re.search(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, re.S)
    assert blok, "prefers-reduced-motion qaydası yoxdur"
    assert "skeleton" in blok.group(1)
