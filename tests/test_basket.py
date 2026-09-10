"""
Səbət müqayisəsi testləri.

LLM YOXDUR - datanı birbaşa DB-yə yazırıq və müqayisə məntiqini yoxlayırıq.
Ən vacib yoxlama: natamam market "ən ucuz" elan olunmamalıdır.
"""

from fastapi.testclient import TestClient

from app.main import app

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
                assert totals["Bravo Market"] == 5.29
                assert totals["Araz Market"] == 5.20
                assert data["best"]["store"] == "Araz Market"
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

                assert by_store["Bravo Market"]["complete"] is False
                assert by_store["Bravo Market"]["missing"] == ["çay"]
                assert by_store["Araz Market"]["complete"] is True
                assert data["best"]["store"] == "Araz Market"
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
                assert totals["Araz Market"] == 9.45
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
