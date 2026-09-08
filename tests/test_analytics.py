"""
Qiymət tarixçəsi və endirim yoxlaması testləri.

Real bazada hələ 2-3 müşahidə var, ona görə "təsdiqlənib" və "şübhəli"
halları təbii yolla yaranmır. Testdə həmin halları ÖZÜMÜZ quraşdırırıq:
məhsul + bir neçə qiymət sətri yazırıq, sonra hökmü yoxlayırıq.

Ən vacib test `test_tarixcesiz_iddia_saxta_elan_edilmir` - sistem bilmədiyini
"saxta" adlandırmamalıdır. Bu, funksiyanın bütün mənasıdır: yanlış ittiham
faydasız xəbərdarlıqdan da pisdir.
"""

import pytest
from fastapi.testclient import TestClient

from app.analytics import check_discounts, price_history, tracked_groups
from app.db import db_cursor
from app.main import app

# REAL marketlər. Tarixçə və endirim yoxlaması yalnız `app/stores.py`
# reyestrindəki dörd marketi götürür - uydurma slug ilə yaradılmış market
# cavaba ümumiyyətlə düşmür (bax `conftest.make_store`).
#
# Adlar da REYESTRDƏN gəlir: cavabda bazadakı sərbəst ad yox, marketin
# kanonik adı qayıdır.
STORE_A = "Araz Market"
STORE_B = "Bravo Market"


def _store(cur, name: str, slug: str) -> int:
    cur.execute(
        "INSERT INTO stores (slug, name) VALUES (?, ?) ON CONFLICT(slug) DO NOTHING",
        (slug, name),
    )
    cur.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
    return cur.fetchone()[0]


@pytest.fixture
def senaryo():
    """
    Süni məhsul + qiymət tarixçəsi qurur, test bitəndə hamısını silir.

    `qur(...)` çağırışı qiymət sətirlərini SIRA ilə yazır; seen_at dəyərləri
    əl ilə verilir ki, "əvvəl/sonra" məntiqi dəqiq yoxlana bilsin.
    """
    created = {"products": [], "prices": [], "catalog": None, "stores": []}

    def qur(group_key: str, name: str, rows: list[dict]) -> None:
        with db_cursor() as cur:
            store_a = _store(cur, "Araz", "araz")
            store_b = _store(cur, "Bravo", "bravo")
            created["stores"] = [store_a, store_b]

            cur.execute(
                "INSERT INTO catalogs (store_id, file_hash, file_path, source_type, status) "
                "VALUES (?, ?, 'data/raw/test.png', 'image', 'extracted')",
                (store_a, f"analitika-{group_key}"),
            )
            catalog_id = cur.lastrowid
            created["catalog"] = catalog_id

            for i, row in enumerate(rows):
                cur.execute(
                    "INSERT INTO products (canonical_key, name, group_key) VALUES (?, ?, ?)",
                    (f"{group_key}|{i}", name, group_key),
                )
                product_id = cur.lastrowid
                created["products"].append(product_id)

                store_id = store_b if row.get("store") == "b" else store_a
                cur.execute(
                    "INSERT INTO prices (product_id, store_id, catalog_id, price, "
                    "                    old_price, unit_price, seen_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        product_id,
                        store_id,
                        catalog_id,
                        row["price"],
                        row.get("old_price"),
                        row.get("unit_price"),
                        row["seen_at"],
                    ),
                )
                created["prices"].append(cur.lastrowid)

    yield qur

    with db_cursor() as cur:
        if created["catalog"]:
            cur.execute("DELETE FROM prices WHERE catalog_id = ?", (created["catalog"],))
            cur.execute("DELETE FROM catalogs WHERE id = ?", (created["catalog"],))
        for product_id in created["products"]:
            cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
        # MARKET SƏTRİ SİLİNMİR: indi bunlar reyestr marketləridir (`araz`,
        # `bravo`) və digər test modulları da onları işlədir. Silsək, nəticə
        # testlərin SIRASINDAN asılı olardı.


def _find(group_key: str):
    """Ən son yazılmış sətri tapır (check_discounts id-yə görə azalan sıralayır)."""
    for check in check_discounts(limit=200):
        if check.group_key == group_key:
            return check
    return None


# ------------------------------------------------------------------ hökmlər


def test_tarixcesiz_iddia_saxta_elan_edilmir(senaryo):
    """Bilmədiyimizi "saxta" adlandırmamalıyıq - yanlış ittiham ən pis səhvdir."""
    senaryo("test|yeni|mehsul", "Yeni məhsul", [
        {"price": 5.99, "old_price": 9.99, "seen_at": "2026-09-01 10:00:00"},
    ])
    check = _find("test|yeni|mehsul")
    assert check.verdict == "tesdiqlenmeyib"
    assert check.observations == 0
    assert "görməmişik" in " ".join(check.reasons)


def test_kohne_qiymet_tarixcede_varsa_tesdiqlenir(senaryo):
    senaryo("test|tesdiq|mehsul", "Təsdiqlənən məhsul", [
        {"price": 9.90, "seen_at": "2026-08-01 10:00:00"},
        {"price": 5.99, "old_price": 9.90, "seen_at": "2026-09-01 10:00:00"},
    ])
    check = _find("test|tesdiq|mehsul")
    assert check.verdict == "tesdiqlenib"
    assert check.max_seen == 9.90
    assert "görmüşük" in " ".join(check.reasons)


def test_sisirdilmis_kohne_qiymet_subheli_sayilir(senaryo):
    """Məhsul həmişə ~4 AZN olub, indi "köhnə qiymət 12 AZN" yazılır."""
    senaryo("test|subheli|mehsul", "Şübhəli məhsul", [
        {"price": 4.00, "seen_at": "2026-08-01 10:00:00"},
        {"price": 4.20, "seen_at": "2026-08-15 10:00:00"},
        {"price": 5.99, "old_price": 12.00, "seen_at": "2026-09-01 10:00:00"},
    ])
    check = _find("test|subheli|mehsul")
    assert check.verdict == "subheli"
    assert check.max_seen == 4.20
    assert "12.00" in " ".join(check.reasons)


def test_hedden_artiq_derin_endirim_subhelidir(senaryo):
    """Ərzaqda 85% endirim olmur - ya OCR səhvi, ya uydurma."""
    senaryo("test|derin|mehsul", "Dərin endirim", [
        {"price": 1.50, "old_price": 10.00, "seen_at": "2026-09-01 10:00:00"},
    ])
    check = _find("test|derin|mehsul")
    assert check.verdict == "subheli"
    assert "endirim" in " ".join(check.reasons).lower()


def test_kohne_qiymet_yoxdursa_hokm_verilmir(senaryo):
    senaryo("test|endirimsiz|mehsul", "Endirimsiz", [
        {"price": 3.50, "seen_at": "2026-09-01 10:00:00"},
    ])
    check = _find("test|endirimsiz|mehsul")
    assert check.verdict == "endirim_yoxdur"
    assert check.discount_pct is None


def test_kohne_qiymet_cari_qiymetden_kicikdirse_endirim_sayilmir(senaryo):
    """OCR qiymətləri yerini dəyişə bilər - bu, endirim deyil."""
    senaryo("test|tersine|mehsul", "Tərsinə", [
        {"price": 9.00, "old_price": 5.00, "seen_at": "2026-09-01 10:00:00"},
    ])
    check = _find("test|tersine|mehsul")
    assert check.verdict == "endirim_yoxdur"


def test_qonsu_marketde_ucuzdursa_xeberdarliq_verilir(senaryo):
    """Endirim həqiqi ola bilər, amma yenə də sərfəli olmaya bilər."""
    senaryo("test|qonsu|mehsul", "Qonşu market", [
        {"price": 3.00, "store": "b", "seen_at": "2026-08-01 10:00:00"},
        {"price": 4.00, "old_price": 4.50, "seen_at": "2026-09-01 10:00:00"},
    ])
    check = _find("test|qonsu|mehsul")
    assert check.cheaper_elsewhere is not None
    assert check.cheaper_elsewhere["price"] == 3.00
    assert "daha ucuzdur" in " ".join(check.reasons)


# ------------------------------------------------------------------ tarixçə


def test_tarixce_qrup_uzre_yigilir(senaryo):
    """Fərqli marketdəki eyni məhsul bir qrafikə düşməlidir."""
    senaryo("test|tarixce|mehsul", "Tarixçə məhsulu", [
        {"price": 2.00, "unit_price": 4.0, "seen_at": "2026-08-01 10:00:00"},
        {"price": 2.20, "store": "b", "unit_price": 4.4, "seen_at": "2026-08-10 10:00:00"},
        {"price": 1.80, "unit_price": 3.6, "seen_at": "2026-09-01 10:00:00"},
    ])
    history = price_history("test|tarixce|mehsul")
    assert len(history["points"]) == 3
    assert set(history["stores"]) == {STORE_A, STORE_B}
    # Sıra vaxta görə olmalıdır - qrafik əks halda zigzaq çəkər
    dates = [p["seen_at"] for p in history["points"]]
    assert dates == sorted(dates)


def test_qrup_siyahisi_en_cox_musahideni_evvele_qoyur(senaryo):
    senaryo("test|coxmusahide|mehsul", "Çox müşahidə", [
        {"price": 1.00, "seen_at": "2026-08-01 10:00:00"},
        {"price": 1.10, "seen_at": "2026-08-02 10:00:00"},
        {"price": 1.20, "seen_at": "2026-08-03 10:00:00"},
        {"price": 1.30, "seen_at": "2026-08-04 10:00:00"},
    ])
    groups = tracked_groups(limit=50)
    ours = next(g for g in groups if g["group_key"] == "test|coxmusahide|mehsul")
    assert ours["observations"] == 4
    # Bizimki 4 müşahidə ilə siyahının yuxarı hissəsində olmalıdır
    assert groups.index(ours) == 0


def test_bos_qrup_bos_netice_verir():
    history = price_history("belə|qrup|yoxdur")
    assert history["points"] == []


# ------------------------------------------------------------------ API


def test_endpointler_cavab_verir():
    with TestClient(app) as client:
        assert client.get("/api/analytics/groups").status_code == 200

        res = client.get("/api/analytics/discounts?limit=10")
        assert res.status_code == 200
        data = res.json()
        assert "counts" in data and "items" in data

        assert client.get("/api/analytics/history?group_key=%20").status_code == 400
