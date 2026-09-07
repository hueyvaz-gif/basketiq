"""
Səbət müqayisəsi testləri.

LLM YOXDUR - datanı birbaşa DB-yə yazırıq və müqayisə məntiqini yoxlayırıq.
Ən vacib yoxlama: natamam market "ən ucuz" elan olunmamalıdır.
"""

import pytest
from fastapi.testclient import TestClient

from app.db import db_cursor, get_connection
from app.main import app

@pytest.fixture
def empty_basket():
    """Hər test öz səbəti ilə işləsin - ümumi səbətin vəziyyətindən asılı olmasın."""
    with db_cursor() as cur:
        cur.execute("INSERT INTO baskets (name) VALUES ('test')")
        basket_id = cur.lastrowid
    yield basket_id
    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE basket_id = ?", (basket_id,))
        cur.execute("DELETE FROM baskets WHERE id = ?", (basket_id,))


@pytest.fixture
def sample_data():
    """
    İki market, üç məhsul:
      - süd    : hər iki marketdə (Bravo ucuz)
      - düyü   : hər iki marketdə (Araz ucuz)
      - çay    : yalnız Araz-da
    Süd iki ayrı product sətridir, amma eyni group_key altındadır -
    yəni matching işləmiş kimi.
    """
    created = {"stores": [], "products": [], "catalogs": []}

    with db_cursor() as cur:
        for slug, name in [("t-bravo", "TestBravo"), ("t-araz", "TestAraz")]:
            cur.execute("INSERT INTO stores (slug, name) VALUES (?, ?)", (slug, name))
            created["stores"].append(cur.lastrowid)

        for i, store_id in enumerate(created["stores"]):
            cur.execute(
                "INSERT INTO catalogs (store_id, file_hash, file_path, source_type) "
                "VALUES (?, ?, ?, 'image')",
                (store_id, f"testhash{i}", f"data/raw/test{i}.png"),
            )
            created["catalogs"].append(cur.lastrowid)

        # (canonical_key, group_key, ad)
        rows = [
            ("t|sud|bravo|1l", "t|sud|1l", "süd"),      # eyni qrup
            ("t|sud|araz|1l", "t|sud|1l", "süd"),       # eyni qrup
            ("t|duyu|1kg", "t|duyu|1kg", "düyü"),
            ("t|cay|250g", "t|cay|250g", "çay"),
        ]
        for key, group, name in rows:
            cur.execute(
                "INSERT INTO products (canonical_key, name, brand, size_value, size_unit, "
                "                      category, group_key) VALUES (?, ?, NULL, 1, 'l', 'digər', ?)",
                (key, name, group),
            )
            created["products"].append(cur.lastrowid)

    sud_bravo, sud_araz, duyu, cay = created["products"]
    bravo, araz = created["stores"]
    cat_bravo, cat_araz = created["catalogs"]

    with db_cursor() as cur:
        prices = [
            (sud_bravo, bravo, cat_bravo, 1.89),
            (sud_araz, araz, cat_araz, 2.05),
            (duyu, bravo, cat_bravo, 3.40),
            (duyu, araz, cat_araz, 3.15),
            (cay, araz, cat_araz, 3.80),
        ]
        for product_id, store_id, catalog_id, price in prices:
            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price, unit_price) "
                "VALUES (?, ?, ?, ?, ?)",
                (product_id, store_id, catalog_id, price, price),
            )

    yield {"stores": created["stores"], "sud": sud_bravo, "duyu": duyu, "cay": cay}

    # Təmizlik: test datası real DB-də qalmasın
    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE product_id IN "
                    "(SELECT id FROM products WHERE canonical_key LIKE 't|%')")
        cur.execute("DELETE FROM prices WHERE catalog_id IN "
                    f"({','.join('?' * len(created['catalogs']))})", created["catalogs"])
        cur.execute("DELETE FROM catalogs WHERE id IN "
                    f"({','.join('?' * len(created['catalogs']))})", created["catalogs"])
        cur.execute("DELETE FROM products WHERE canonical_key LIKE 't|%'")
        cur.execute("DELETE FROM stores WHERE slug LIKE 't-%'")


def add(client, basket_id, product_id, qty=1):
    return client.post(f"/api/basket/items?basket_id={basket_id}",
                       json={"product_id": product_id, "qty": qty})


def compare(client, basket_id):
    return client.get(f"/api/basket/compare?basket_id={basket_id}").json()


class TestSebet:
    def test_bos_sebet_cokmur(self, empty_basket):
        basket_id = empty_basket
        with TestClient(app) as client:
            data = compare(client, basket_id)
            assert data["items"] == [] and data["best"] is None

    def test_mehsul_elave_ve_silme(self, sample_data, empty_basket):
        basket_id = empty_basket
        with TestClient(app) as client:
            assert add(client, basket_id, sample_data["sud"]).status_code == 200
            assert len(client.get(f"/api/basket?basket_id={basket_id}").json()["items"]) == 1

            client.delete(f"/api/basket/items/{sample_data['sud']}?basket_id={basket_id}")
            assert client.get(f"/api/basket?basket_id={basket_id}").json()["items"] == []

    def test_olmayan_mehsul_404(self, empty_basket):
        basket_id = empty_basket
        with TestClient(app) as client:
            assert add(client, basket_id, 999999).status_code == 404


class TestMuqayise:
    def test_qrup_uzre_muqayise_isleyir(self, sample_data, empty_basket):
        """
        Səbətə Bravo-nun südü əlavə olunur, amma müqayisədə Araz-ın südü də
        görünməlidir - çünki group_key eynidir.
        """
        basket_id = empty_basket
        with TestClient(app) as client:
            add(client, basket_id, sample_data["sud"])
            try:
                data = compare(client, basket_id)
                item = data["items"][0]
                assert item["available_in"] == 2, "qrup üzrə axtarış işləmir"
            finally:
                client.delete(f"/api/basket/items/{sample_data['sud']}?basket_id={basket_id}")

    def test_en_ucuz_market_duzgun_secilir(self, sample_data, empty_basket):
        basket_id = empty_basket
        with TestClient(app) as client:
            add(client, basket_id, sample_data["sud"])    # Bravo 1.89 / Araz 2.05
            add(client, basket_id, sample_data["duyu"])   # Bravo 3.40 / Araz 3.15
            try:
                data = compare(client, basket_id)
                totals = {s["store"]: s["total"] for s in data["stores"]}
                assert totals["TestBravo"] == 5.29
                assert totals["TestAraz"] == 5.20
                assert data["best"]["store"] == "TestAraz"
                assert data["savings"] == 0.09
            finally:
                for pid in (sample_data["sud"], sample_data["duyu"]):
                    client.delete(f"/api/basket/items/{pid}?basket_id={basket_id}")

    def test_natamam_market_en_ucuz_elan_edilmir(self, sample_data, empty_basket):
        """
        ƏN VACİB TEST. Çay yalnız Araz-da var. Bravo-nun cəmi kiçik görünür,
        çünki çayı satmır - amma o, "ən ucuz" ola BİLMƏZ.
        """
        basket_id = empty_basket
        with TestClient(app) as client:
            add(client, basket_id, sample_data["sud"])
            add(client, basket_id, sample_data["cay"])
            try:
                data = compare(client, basket_id)
                by_store = {s["store"]: s for s in data["stores"]}

                assert by_store["TestBravo"]["complete"] is False
                assert by_store["TestBravo"]["missing"] == ["çay"]
                assert by_store["TestAraz"]["complete"] is True
                assert data["best"]["store"] == "TestAraz"
            finally:
                for pid in (sample_data["sud"], sample_data["cay"]):
                    client.delete(f"/api/basket/items/{pid}?basket_id={basket_id}")

    def test_miqdar_ceme_tesir_edir(self, sample_data, empty_basket):
        basket_id = empty_basket
        with TestClient(app) as client:
            add(client, basket_id, sample_data["duyu"], qty=3)   # 3.15 * 3 = 9.45
            try:
                data = compare(client, basket_id)
                totals = {s["store"]: s["total"] for s in data["stores"]}
                assert totals["TestAraz"] == 9.45
            finally:
                client.delete(f"/api/basket/items/{sample_data['duyu']}?basket_id={basket_id}")

    def test_her_mehsulda_ucuz_market_isarelenir(self, sample_data, empty_basket):
        basket_id = empty_basket
        with TestClient(app) as client:
            add(client, basket_id, sample_data["sud"])
            add(client, basket_id, sample_data["duyu"])
            try:
                data = compare(client, basket_id)
                bravo, araz = sample_data["stores"]
                cheapest = {i["label"]: i["cheapest_store_id"] for i in data["items"]}
                assert cheapest["süd"] == bravo
                assert cheapest["düyü"] == araz
            finally:
                for pid in (sample_data["sud"], sample_data["duyu"]):
                    client.delete(f"/api/basket/items/{pid}?basket_id={basket_id}")
