"""
İnsan yoxlaması (ADDIM 5) — `/api/match/review`, `/api/match/decide`, `/admin/matches`.

Bu ekran bazanı DƏYİŞİR: düymə qrupları birləşdirir və dağıdır. Ona görə
testlər həm cavabın formasını, həm də düymənin bazada nə etdiyini yoxlayır.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import db_cursor
from app.main import app

client = TestClient(app)


@pytest.fixture
def pending_ayran():
    """
    Araz kataloqunda ölçüsüz «ayran [Azərsüd]», Bravo rəfində «Azərsüd Ayran 1l»
    və bir Bravo məhsulu daha (eyni market qadağasını yoxlamaq üçün).
    Aralarında `pending` qərarı - maşın ölçünü bilmədiyi üçün soruşur.
    """
    with db_cursor() as cur:
        ids = {}
        for slug, name in (("araz", "Araz"), ("bravo", "Bravo")):
            cur.execute(
                "INSERT INTO stores (slug, name) VALUES (?, ?) ON CONFLICT(slug) DO NOTHING",
                (slug, name),
            )
            cur.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
            ids[slug] = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, source_type) "
            "VALUES (?, 'trhash-review', 'data/raw/tr.png', 'image')",
            (ids["araz"],),
        )
        catalog_id = cur.lastrowid
        made = {}
        for tag, key, name, brand in (
            ("araz", "tr|a|ayran", "ayran", "Azərsüd"),
            ("bravo", "tr|b|ayran", "Azərsüd Ayran 1l", None),
            ("bravo2", "tr|c|ayran", "Azərsüd Ayran 290ml", None),
        ):
            cur.execute(
                "INSERT INTO products (canonical_key, name, brand, group_key) VALUES (?, ?, ?, ?)",
                (key, name, brand, key),
            )
            made[tag] = cur.lastrowid
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price, raw_line) "
            "VALUES (?, ?, ?, 0.89, 'Azərsüd ayran 0,5 l 0,89')",
            (made["araz"], ids["araz"], catalog_id),
        )
        for tag, price in (("bravo", 1.29), ("bravo2", 0.65)):
            cur.execute(
                "INSERT INTO price_snapshots (product_id, store_id, price, source, observed_at) "
                "VALUES (?, ?, ?, 'site', '2026-09-11 07:00:00')",
                (made[tag], ids["bravo"], price),
            )
        cur.execute(
            "INSERT INTO match_decisions (a_id, b_id, decision, source, similarity, reason) "
            "VALUES (?, ?, 'pending', 'auto', 1.0, 'ölçü bilinmir')",
            (made["araz"], made["bravo"]),
        )

    yield made

    with db_cursor() as cur:
        marks = ",".join("?" * len(made))
        cur.execute(f"DELETE FROM price_snapshots WHERE product_id IN ({marks})", list(made.values()))
        cur.execute("DELETE FROM prices WHERE catalog_id = ?", (catalog_id,))
        cur.execute("DELETE FROM catalogs WHERE id = ?", (catalog_id,))
        cur.execute(f"DELETE FROM products WHERE id IN ({marks})", list(made.values()))


def _our_pair(data, made):
    return next(
        (p for p in data["pairs"] if {p["a_id"], p["b_id"]} == {made["araz"], made["bravo"]}),
        None,
    )


class TestNovbe:
    def test_gozleyen_cut_kart_ucun_hazir_gelir(self, pending_ayran):
        data = client.get("/api/match/review?status=pending&limit=200").json()
        pair = _our_pair(data, pending_ayran)
        assert pair is not None
        assert pair["reason"] == "ölçü bilinmir"
        assert data["counts"]["pending"] >= 1

        araz = pair["a"] if pair["a_id"] == pending_ayran["araz"] else pair["b"]
        assert araz["label"] == "Azərsüd ayran"
        # İnsan ölçünü OCR sətrində görə bilsin
        assert araz["offers"][0]["raw_line"] == "Azərsüd ayran 0,5 l 0,89"
        assert araz["offers"][0]["store"] == "Araz Market"

    def test_ref_qiymeti_de_gorunur(self, pending_ayran):
        data = client.get("/api/match/review?status=pending&limit=200").json()
        pair = _our_pair(data, pending_ayran)
        bravo = pair["b"] if pair["b_id"] == pending_ayran["bravo"] else pair["a"]
        assert bravo["offers"][0]["price"] == 1.29
        assert bravo["offers"][0]["layer"] == "site"

    def test_olcu_addan_oxunur_yalniz_kataloq_terefi_olcusuz_qalir(self, pending_ayran):
        """
        Bravo ölçünü adda yazır («Azərsüd Ayran 1l»), `size_value` boşdur.
        Kart hər iki tərəfdə «ölçü bilinmir» yazsaydı, insanın görməli olduğu
        siqnal (məhz KATALOQ tərəfi ölçüsüzdür) itərdi. Brauzerdə belə görüldü.
        """
        data = client.get("/api/match/review?status=pending&limit=200").json()
        pair = _our_pair(data, pending_ayran)
        by_id = {pair["a_id"]: pair["a"], pair["b_id"]: pair["b"]}
        assert by_id[pending_ayran["bravo"]]["size"] == "1 l"
        assert by_id[pending_ayran["araz"]]["size"] == ""

    def test_namelum_novbe_400(self):
        assert client.get("/api/match/review?status=hamisi").status_code == 400


class TestQerar:
    def test_beli_birlesdirir_ve_novbeden_cixarir(self, pending_ayran):
        res = client.post("/api/match/decide", json={
            "a_id": pending_ayran["araz"], "b_id": pending_ayran["bravo"], "same": True,
        })
        assert res.status_code == 200
        assert res.json()["applied"] is True

        with db_cursor() as cur:
            cur.execute("SELECT group_key FROM products WHERE id IN (?, ?)",
                        (pending_ayran["araz"], pending_ayran["bravo"]))
            assert len({r["group_key"] for r in cur.fetchall()}) == 1

        data = client.get("/api/match/review?status=pending&limit=200").json()
        assert _our_pair(data, pending_ayran) is None

    def test_xeyr_ayri_saxlayir(self, pending_ayran):
        res = client.post("/api/match/decide", json={
            "a_id": pending_ayran["araz"], "b_id": pending_ayran["bravo"], "same": False,
        })
        assert res.json()["applied"] is True
        with db_cursor() as cur:
            cur.execute("SELECT decision, source FROM match_decisions WHERE a_id = ? AND b_id = ?",
                        (min(pending_ayran["araz"], pending_ayran["bravo"]),
                         max(pending_ayran["araz"], pending_ayran["bravo"])))
            assert tuple(cur.fetchone()) == ("different", "human")

    def test_qadagaya_dusen_beli_tetbiq_olunmur_amma_deyilir(self, pending_ayran):
        """İki Bravo məhsulu bir qrupa girə bilməz - ekran bunu gizlətməməlidir."""
        res = client.post("/api/match/decide", json={
            "a_id": pending_ayran["bravo"], "b_id": pending_ayran["bravo2"], "same": True,
        })
        assert res.status_code == 200
        assert res.json()["applied"] is False

    def test_olmayan_mehsul_404(self):
        res = client.post("/api/match/decide", json={"a_id": 999998, "b_id": 999999, "same": True})
        assert res.status_code == 404

    def test_eyni_mehsul_ozu_ile_400(self, pending_ayran):
        res = client.post("/api/match/decide", json={
            "a_id": pending_ayran["araz"], "b_id": pending_ayran["araz"], "same": True,
        })
        assert res.status_code == 400


class TestSehife:
    def test_admin_aciq_olanda_sehife_acilir(self):
        res = client.get("/admin/matches")
        assert res.status_code == 200
        assert 'id="matchList"' in res.text

    def test_admin_bagli_olanda_404(self):
        əvvəlki = settings.admin_enabled
        settings.admin_enabled = False
        try:
            assert client.get("/admin/matches").status_code == 404
            assert client.get("/api/match/review").status_code == 404
        finally:
            settings.admin_enabled = əvvəlki
