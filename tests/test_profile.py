"""
Profil və profil əsaslı tövsiyə testləri.

`recommend()` müqayisə nəticəsini PARAMETR kimi alır - bazaya toxunmadan
istənilən vəziyyəti qura bilirik. Bu, qəsdən belədir: tövsiyə məntiqi
qiymətlərin haradan gəldiyini bilməməlidir.

Testlərin əsas sualı: profil dəyişəndə TÖVSİYƏ dəyişirmi? Profil yalnız
ekranda görünüb qərara təsir etmirsə, o, bəzəkdir.
"""

import pytest
from fastapi.testclient import TestClient

from ai.advisor import build_facts
from app.db import db_cursor
from app.main import app
from app.profile import Profile, get_profile, save_profile
from app.recommend import base_name_key, recommend

ARAZ, BRAVO = 1, 2


def compare_data(items, stores=None, best=None, savings=None):
    """compare() çıxışının sadələşdirilmiş nüsxəsi."""
    return {
        "basket_id": 1,
        "items": items,
        "stores": stores or [],
        "best": best,
        "savings": savings,
    }


def item(label, qty=1, prices=None, product_id=1):
    return {
        "product_id": product_id,
        "label": label,
        "size": "",
        "qty": qty,
        "prices": {str(sid): {"price": p} for sid, p in (prices or {}).items()},
        "cheapest_store_id": min(prices, key=prices.get) if prices else None,
        "available_in": len(prices or {}),
    }


def store(store_id, name, total, covered, complete=True, diff=None):
    return {
        "store_id": store_id,
        "store": name,
        "total": total,
        "covered": covered,
        "missing": [],
        "cheapest_count": 0,
        "complete": complete,
        "diff": diff,
    }


# Araz cəmi ucuzdur, amma südü Bravo daha ucuz satır ->
# bölmək 0.50 AZN qənaət edir.
SENARYO = compare_data(
    items=[
        item("Milla süd", prices={ARAZ: 2.00, BRAVO: 1.50}, product_id=1),
        item("basmati düyü", prices={ARAZ: 3.00, BRAVO: 3.50}, product_id=2),
    ],
    stores=[
        store(ARAZ, "Araz", 5.00, 2),
        store(BRAVO, "Bravo", 5.00, 2),
    ],
    best=store(ARAZ, "Araz", 5.00, 2),
)


@pytest.fixture(autouse=True)
def profil_qorunur():
    """Testlər real profili dəyişməsin."""
    before = get_profile()
    yield
    save_profile(before)


# ------------------------------------------------------------------ plan seçimi


def test_tek_markete_gedən_adama_bolme_teklif_edilmir():
    rec = recommend(SENARYO, Profile(max_stores=1))
    assert rec.plan == "tek_market"
    assert rec.stores == ["Araz"]
    assert rec.total == 5.00


def test_tek_market_planinda_itirilen_qenaet_gosterilir():
    """İstifadəçi "nə itirirəm?" sualının cavabını görməlidir."""
    rec = recommend(SENARYO, Profile(max_stores=1))
    assert any("qənaət edərdin" in n for n in rec.notes)


def test_iki_markete_hazir_adama_bolme_teklif_olunur():
    rec = recommend(SENARYO, Profile(max_stores=2, min_split_saving=0.10))
    assert rec.plan == "bolunmus"
    assert set(rec.stores) == {"Araz", "Bravo"}
    assert rec.total == pytest.approx(4.50)
    assert rec.split_saving == pytest.approx(0.50)


def test_qenaet_hedden_azdirsa_bolme_teklif_edilmir():
    """0.50 AZN üçün ikinci markete getmək praktik deyil."""
    rec = recommend(SENARYO, Profile(max_stores=2, min_split_saving=2.00))
    assert rec.plan == "tek_market"
    assert any("həddən" in n for n in rec.notes)
    # Rəqəm yenə də görünməlidir
    assert rec.split_saving == pytest.approx(0.50)


def test_bolme_cox_market_teleb_edirse_tek_market_secilir():
    üç_market = compare_data(
        items=[
            item("A", prices={1: 1.0, 2: 2.0, 3: 2.0}, product_id=1),
            item("B", prices={1: 2.0, 2: 1.0, 3: 2.0}, product_id=2),
            item("C", prices={1: 2.0, 2: 2.0, 3: 1.0}, product_id=3),
        ],
        stores=[store(1, "A market", 5.0, 3), store(2, "B market", 5.0, 3),
                store(3, "C market", 5.0, 3)],
        best=store(1, "A market", 5.0, 3),
    )
    rec = recommend(üç_market, Profile(max_stores=2, min_split_saving=0.10))
    assert rec.plan == "tek_market"
    assert any("market tələb edir" in n for n in rec.notes)


def test_bos_sebet():
    rec = recommend(compare_data(items=[]), Profile())
    assert rec.plan == "yoxdur"
    assert "boş" in rec.notes[0].lower()


def test_hec_bir_market_tam_deyilse_tek_market_teleb_edilende_izah_verilir():
    natamam = compare_data(
        items=[
            item("A", prices={1: 1.0}, product_id=1),
            item("B", prices={2: 1.0}, product_id=2),
        ],
        stores=[store(1, "A market", 1.0, 1, complete=False),
                store(2, "B market", 1.0, 1, complete=False)],
        best=None,
    )
    rec = recommend(natamam, Profile(max_stores=1))
    assert rec.plan == "yoxdur"
    assert any("profili dəyiş" in n for n in rec.notes)


# ------------------------------------------------------------------ büdcə


def test_budce_asilanda_en_bahali_mehsullar_gosterilir():
    rec = recommend(SENARYO, Profile(max_stores=1, weekly_budget=4.00))
    assert rec.budget["fits"] is False
    assert rec.budget["over"] == pytest.approx(1.00)
    assert any("büdcəni" in w for w in rec.warnings)
    # Ən bahalı məhsul birinci olmalıdır
    assert rec.budget["biggest_items"][0]["label"] == "basmati düyü"


def test_budce_sigirsa_xeberdarliq_yoxdur():
    rec = recommend(SENARYO, Profile(max_stores=1, weekly_budget=50.0))
    assert rec.budget["fits"] is True
    assert not any("büdcəni" in w for w in rec.warnings)


def test_budce_yoxdursa_yoxlanmir():
    rec = recommend(SENARYO, Profile(max_stores=1, weekly_budget=None))
    assert rec.budget is None


# ------------------------------------------------------------------ istisnalar


def test_istenilmeyen_mehsul_xeberdarliq_verir():
    rec = recommend(SENARYO, Profile(max_stores=1, avoid=["süd"]))
    assert any("Milla süd" in w for w in rec.warnings)


def test_istisna_siyahisi_bosdursa_xeberdarliq_yoxdur():
    rec = recommend(SENARYO, Profile(max_stores=1, avoid=[]))
    assert not any("istəmədiyin" in w for w in rec.warnings)


# ------------------------------------------------------------------ qablaşdırma


def test_olcusuz_acar():
    assert base_name_key("milla|sud|1l") == "milla|sud"
    assert base_name_key("milla|sud|0.5kg") == "milla|sud"
    assert base_name_key("milla|sud") == "milla|sud"
    # Ölçü olmayan sonuncu seqment kəsilməməlidir
    assert base_name_key("azercay|cay") == "azercay|cay"


@pytest.fixture
def boyuk_qablasdirma():
    """Eyni məhsulun 1 L və 2 L variantı - 2 L-in litri ucuzdur."""
    created = {"products": [], "catalog": None, "store": None}
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO stores (slug, name) VALUES ('bulk-test', 'Bulk Test') "
            "ON CONFLICT(slug) DO NOTHING"
        )
        cur.execute("SELECT id FROM stores WHERE slug = 'bulk-test'")
        store_id = cur.fetchone()[0]
        created["store"] = store_id

        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, source_type, status) "
            "VALUES (?, 'bulk-hash', 'data/raw/x.png', 'image', 'extracted')",
            (store_id,),
        )
        catalog_id = cur.lastrowid
        created["catalog"] = catalog_id

        for size, price, unit in ((1.0, 2.00, 2.00), (2.0, 3.20, 1.60)):
            cur.execute(
                "INSERT INTO products (canonical_key, name, brand, size_value, "
                "                      size_unit, group_key) "
                "VALUES (?, 'test südü', 'Testmarka', ?, 'l', ?)",
                (f"testmarka|testsudu|{size:g}l", size, f"testmarka|testsudu|{size:g}l"),
            )
            product_id = cur.lastrowid
            created["products"].append((product_id, size))
            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price, unit_price) "
                "VALUES (?, ?, ?, ?, ?)",
                (product_id, store_id, catalog_id, price, unit),
            )

    yield created

    with db_cursor() as cur:
        cur.execute("DELETE FROM prices WHERE catalog_id = ?", (created["catalog"],))
        cur.execute("DELETE FROM catalogs WHERE id = ?", (created["catalog"],))
        for product_id, _ in created["products"]:
            cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
        cur.execute("DELETE FROM stores WHERE id = ?", (created["store"],))


def test_boyuk_aile_ucun_boyuk_qablasdirma_teklif_olunur(boyuk_qablasdirma):
    kicik_id = boyuk_qablasdirma["products"][0][0]
    data = compare_data(
        items=[item("Testmarka test südü", prices={ARAZ: 2.00}, product_id=kicik_id)],
        stores=[store(ARAZ, "Araz", 2.00, 1)],
        best=store(ARAZ, "Araz", 2.00, 1),
    )
    rec = recommend(data, Profile(household_size=5, max_stores=1, prefer_unit_price=True))
    assert rec.bulk_tips, "2 litrlik variant tövsiyə olunmalı idi"
    tip = rec.bulk_tips[0]
    assert tip["better_unit_price"] == 1.60
    assert tip["gain_pct"] == pytest.approx(20.0)


def test_tek_yasayan_ucun_boyuk_qablasdirma_teklif_olunmur(boyuk_qablasdirma):
    """1-2 nəfərlik evdə böyük qablaşdırma xarab olur - qənaət kağız üzərində qalır."""
    kicik_id = boyuk_qablasdirma["products"][0][0]
    data = compare_data(
        items=[item("Testmarka test südü", prices={ARAZ: 2.00}, product_id=kicik_id)],
        stores=[store(ARAZ, "Araz", 2.00, 1)],
        best=store(ARAZ, "Araz", 2.00, 1),
    )
    rec = recommend(data, Profile(household_size=1, max_stores=1))
    assert rec.bulk_tips == []


# ------------------------------------------------------------------ saxlama


def test_hedden_kenar_deyerler_meḥdudlasdirilir():
    saved = save_profile(Profile(household_size=999, max_stores=99, weekly_budget=-5))
    assert saved.household_size == 20
    assert saved.max_stores == 5
    assert saved.weekly_budget is None


def test_istisna_sozleri_kicik_herfe_cevrilir():
    saved = save_profile(Profile(avoid=["  DONUZ ", "Alkoqol", ""]))
    assert saved.avoid == ["donuz", "alkoqol"]


# ------------------------------------------------------------------ advisor


def test_profil_modele_gonderilen_faktlara_dusur():
    """Model profili görməsə, tək markete gedən adama "iki markete get" deyər."""
    facts = build_facts(SENARYO, "3 nəfərlik ev; yalnız bir markete gedir")
    assert facts.startswith("İSTİFADƏÇİ:")
    assert "bir markete gedir" in facts


def test_profilsiz_faktlar_evvelki_kimi_qalir():
    facts = build_facts(SENARYO)
    assert not facts.startswith("İSTİFADƏÇİ:")
    assert "MARKETLƏR ÜZRƏ CƏM:" in facts


# ------------------------------------------------------------------ API


def test_profil_endpointleri():
    with TestClient(app) as client:
        res = client.put("/api/profile", json={
            "household_size": 4, "weekly_budget": 90, "max_stores": 2,
            "min_split_saving": 1.5, "prefer_unit_price": True, "avoid": ["donuz"],
        })
        assert res.status_code == 200
        data = res.json()
        assert data["household_size"] == 4
        assert "4 nəfərlik ev" in data["summary"]

        assert client.get("/api/profile").json()["weekly_budget"] == 90

        plan = client.get("/api/profile/recommend")
        assert plan.status_code == 200
        assert "plan" in plan.json()
