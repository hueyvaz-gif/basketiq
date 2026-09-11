"""
Səbət müqayisəsi İKİ qiymət qatını oxuyur (ADDIM 4a).

NİYƏ AYRICA TEST? Əvvəl `_latest_prices_by_group` yalnız `prices` (kataloq)
cədvəlini oxuyurdu. Bravonun bütün məhsulları mağaza qatındadır
(`price_snapshots`), yəni səbətdəki Bravo məhsulu «heç bir marketdə
qiyməti yoxdur» görünürdü. Səhv SƏSSİZ idi: cavab gəlirdi, sadəcə Bravo
sütunu boş qalırdı — və uyğunlaşdırma nə qədər yaxşı işləsə də, səbətdə
heç nə dəyişmirdi.
"""

import pytest
from fastapi.testclient import TestClient

from app.db import db_cursor
from app.main import app


@pytest.fixture
def milk_two_layers():
    """
    Eyni qrupda iki məhsul:
      Araz  — kataloq qiyməti 2.05
      Bravo — KÖHNƏ kataloq iddiası 2.49 (09-01) + DAHA YENİ rəf qiyməti 1.89 (09-11)
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
        catalogs = []
        for i, slug in enumerate(("araz", "bravo")):
            cur.execute(
                "INSERT INTO catalogs (store_id, file_hash, file_path, source_type) "
                "VALUES (?, ?, 'data/raw/tl.png', 'image')",
                (ids[slug], f"tl-layers-{i}"),
            )
            catalogs.append(cur.lastrowid)
        cur.execute(
            "INSERT INTO products (canonical_key, name, brand, size_value, size_unit, group_key) "
            "VALUES ('tl|a|sud', 'süd', 'Milla', 1, 'l', 'tl|sud')"
        )
        araz_p = cur.lastrowid
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key) "
            "VALUES ('tl|b|sud', 'Milla Süd 2 5% 1l', 'tl|sud')"
        )
        bravo_p = cur.lastrowid
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price, raw_line, seen_at) "
            "VALUES (?, ?, ?, 2.05, 'Milla süd 1 l 2,05', '2026-09-10 08:00:00')",
            (araz_p, ids["araz"], catalogs[0]),
        )
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price, raw_line, seen_at) "
            "VALUES (?, ?, ?, 2.49, 'köhnə iddia', '2026-09-01 08:00:00')",
            (bravo_p, ids["bravo"], catalogs[1]),
        )
        bravo_catalog_row = cur.lastrowid
        cur.execute(
            "INSERT INTO price_snapshots (product_id, store_id, price, unit_price, source, observed_at) "
            "VALUES (?, ?, 1.89, 1.89, 'site', '2026-09-11 07:00:00')",
            (bravo_p, ids["bravo"]),
        )

    yield {
        "araz_p": araz_p,
        "araz": ids["araz"],
        "bravo": ids["bravo"],
        "bravo_catalog_row": bravo_catalog_row,
    }

    marks = ",".join("?" * len(catalogs))
    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE product_id IN (?, ?)", (araz_p, bravo_p))
        cur.execute("DELETE FROM price_snapshots WHERE product_id IN (?, ?)", (araz_p, bravo_p))
        cur.execute(f"DELETE FROM prices WHERE catalog_id IN ({marks})", catalogs)
        cur.execute(f"DELETE FROM catalogs WHERE id IN ({marks})", catalogs)
        cur.execute("DELETE FROM products WHERE id IN (?, ?)", (araz_p, bravo_p))


def _item_prices(basket_id, product_id):
    with TestClient(app) as client:
        client.post(f"/api/basket/items?basket_id={basket_id}", json={"product_id": product_id, "qty": 1})
        data = client.get(f"/api/basket/compare?basket_id={basket_id}").json()
    return data["items"][0]


class TestIkiQat:
    def test_bravo_ref_qiymeti_sebete_catir(self, milk_two_layers, empty_basket):
        """Səbətdə ARAZIN südü var — Bravonun rəf qiyməti də görünməlidir."""
        item = _item_prices(empty_basket, milk_two_layers["araz_p"])
        assert item["available_in"] == 2
        assert item["prices"][str(milk_two_layers["bravo"])]["price"] == 1.89

    def test_ref_setrinde_ocr_metni_yoxdur(self, milk_two_layers, empty_basket):
        item = _item_prices(empty_basket, milk_two_layers["araz_p"])
        assert item["prices"][str(milk_two_layers["bravo"])]["raw_line"] is None
        assert item["prices"][str(milk_two_layers["araz"])]["raw_line"] == "Milla süd 1 l 2,05"

    def test_en_yeni_qat_qalib_gelir(self, milk_two_layers, empty_basket):
        """Kataloq iddiası rəf qiymətindən YENİdirsə, o göstərilir — qat yox, vaxt həlledicidir."""
        with db_cursor() as cur:
            cur.execute(
                "UPDATE prices SET seen_at = '2026-09-12 08:00:00' WHERE id = ?",
                (milk_two_layers["bravo_catalog_row"],),
            )
        item = _item_prices(empty_basket, milk_two_layers["araz_p"])
        assert item["prices"][str(milk_two_layers["bravo"])]["price"] == 2.49
