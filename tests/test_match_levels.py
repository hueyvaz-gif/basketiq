"""
Üç pilləli uyğunlaşdırmanın qərar qaydaları (ADDIM 3).

Burada səhv iki cür bahalıdır:
  - avtomatik pillə çox yumşaq olsa, 200 q və 1 kq yağ bir məhsul olur və
    səbət müqayisəsi yanlış marketi «ucuz» göstərir;
  - çox sərt olsa, hər cüt LLM-ə gedir (pul + vaxt) və ya heç birləşmir.

Qaydaların çoxu LLM və baza olmadan yoxlanılır; sonda bazalı testlər
müvəqqəti test bazasında (conftest.py) işləyir.
"""

import pytest

from ai import matcher
from ai.matcher import (
    AUTO_MIN_SIMILARITY,
    LLM_MIN_SIMILARITY,
    Candidate,
    GuardedUnion,
    barcode_candidates,
    classify_candidates,
    split_by_size,
)
from app.db import db_cursor

BRAVO, ARAZ, RAHAT = 2, 15, 1266


def item(pid, name, key, brand=None, stores=(), barcode=None):
    return {
        "id": pid,
        "canonical_key": f"ck{pid}",
        "match_key": key,
        "name": name,
        "brand": brand,
        "size_value": None,
        "size_unit": None,
        "group_key": f"ck{pid}",
        "stores": set(stores),
        "barcode": barcode,
    }


def cand(a, b, score):
    return Candidate(a_id=a, b_id=b, a_text=f"#{a}", b_text=f"#{b}", similarity=score)


class TestHedler:
    def test_hedler_tapsiriqdaki_kimidir(self):
        assert AUTO_MIN_SIMILARITY == 0.90
        assert LLM_MIN_SIMILARITY == 0.75


class TestClassify:
    def test_brend_ve_olcu_eyni_yuksek_bal_avtomatik(self):
        products = [
            item(1, "süd", "milla|sud|1l", brand="Milla", stores=[ARAZ]),
            item(2, "Milla Süd 2 5% 1l", "milla|sud|1l", stores=[BRAVO]),
        ]
        auto, suspicious = classify_candidates(products, [cand(1, 2, 1.0)])
        assert [(c.a_id, c.b_id) for c in auto] == [(1, 2)]
        assert suspicious == []

    def test_olcu_bir_terefde_yoxdursa_subhelidir(self):
        """«President kərə yağı» (ölçüsüz) — 200 q-mı, 1 kq-mı? Avtomatik birləşmir."""
        products = [
            item(1, "kərə yağı", "kere|president|yagi", brand="President", stores=[ARAZ]),
            item(2, "President Kərə Yağı 82% 200qr", "kere|president|yagi|0.2kg", stores=[BRAVO]),
        ]
        auto, suspicious = classify_candidates(products, [cand(1, 2, 1.0)])
        assert auto == []
        assert len(suspicious) == 1

    def test_brend_bilinmirse_subhelidir(self):
        products = [
            item(1, "sirab su", "sirab|su|1.5l", stores=[ARAZ]),
            item(2, "Sirab Su 1.5 L", "sirab|su|1.5l", stores=[BRAVO]),
        ]
        auto, suspicious = classify_candidates(products, [cand(1, 2, 1.0)])
        assert auto == []
        assert len(suspicious) == 1

    def test_orta_bal_subhelidir(self):
        products = [
            item(1, "basmati düyü", "basmati|duyu|1kg", brand="Sultan", stores=[ARAZ]),
            item(2, "Sultan Basmati Düyü Uzun 1kq", "basmati|duyu|sultan|uzun|1kg", stores=[BRAVO]),
        ]
        auto, suspicious = classify_candidates(products, [cand(1, 2, 0.8)])
        assert auto == []
        assert len(suspicious) == 1

    def test_asagi_bal_atilir(self):
        products = [
            item(1, "dondurma", "dondurma|milla", brand="Milla", stores=[ARAZ]),
            item(2, "Milla Vanilli Dondurma Plastik Qabda", "dondurma|milla|plastik|qabda|vanilli", stores=[BRAVO]),
        ]
        auto, suspicious = classify_candidates(products, [cand(1, 2, 0.57)])
        assert auto == [] and suspicious == []


class TestSplitBySize:
    """
    Ölçü YALNIZ BİR tərəfdə bilinirsə LLM-in deyə biləcəyi heç nə yoxdur:
    «Azərsüd ayran» 290 ml-dir, 200 ml-dir, yoxsa 1 l? Model də bilmir.
    Real bazada 310 şübhəli cütdən 236-sı belədir — onlar birbaşa insana gedir.
    """

    def test_bir_terefde_olcu_yoxdursa_insana(self):
        products = [
            item(1, "ayran", "ayran|azersud", brand="Azərsüd", stores=[ARAZ]),
            item(2, "Azərsüd Ayran 290ml", "ayran|azersud|0.29l", stores=[BRAVO]),
        ]
        to_llm, to_human = split_by_size(products, [cand(1, 2, 1.0)])
        assert to_llm == []
        assert len(to_human) == 1

    def test_iki_terefde_olcu_varsa_llm_e(self):
        products = [
            item(1, "basmati düyü", "basmati|duyu|1kg", brand="Sultan", stores=[ARAZ]),
            item(2, "Sultan Basmati Düyü Uzun 1kq", "basmati|duyu|sultan|uzun|1kg", stores=[BRAVO]),
        ]
        to_llm, to_human = split_by_size(products, [cand(1, 2, 0.8)])
        assert len(to_llm) == 1
        assert to_human == []

    def test_iki_terefde_olcu_yoxdursa_llm_e(self):
        """Simmetrikdir: ölçü heç birində yoxdur, LLM ad üzrə qərar verə bilər."""
        products = [
            item(1, "uşaq bezi", "bezi|pampers|usaq", brand="Pampers", stores=[ARAZ]),
            item(2, "Pampers Uşaq Bezi", "bezi|pampers|usaq", stores=[BRAVO]),
        ]
        to_llm, to_human = split_by_size(products, [cand(1, 2, 0.8)])
        assert len(to_llm) == 1
        assert to_human == []


class TestGuardedUnion:
    """Keçişli birləşmənin qarşısı: A=B və A=C təsdiqlənsə belə B=C olmaya bilər."""

    def test_iki_olcu_bir_qrupa_dusmur(self):
        products = [
            item(1, "kərə yağı", "kere|president|yagi", brand="President", stores=[ARAZ]),
            item(2, "President Kərə Yağı 82% 200qr", "kere|president|yagi|0.2kg", stores=[BRAVO]),
            item(3, "President Kərə Yağı 82% 1kq", "kere|president|yagi|1kg", stores=[RAHAT]),
        ]
        union = GuardedUnion(products)
        assert union.union(1, 2) is True
        assert union.union(1, 3) is False
        assert union.find(2) != union.find(3)

    def test_eyni_marketin_iki_mehsulu_bir_qrupa_dusmur(self):
        products = [
            item(1, "süd", "milla|sud|1l", brand="Milla", stores=[ARAZ]),
            item(2, "Milla Süd 2 5% 1l", "milla|sud|1l", stores=[BRAVO]),
            item(3, "Milla Süd Laktozasız 1l", "laktozasiz|milla|sud|1l", stores=[BRAVO]),
        ]
        union = GuardedUnion(products)
        assert union.union(1, 2) is True
        assert union.union(1, 3) is False

    def test_ferqli_marketler_birlesir(self):
        products = [
            item(1, "süd", "milla|sud|1l", brand="Milla", stores=[ARAZ]),
            item(2, "süd", "milla|sud|1l", brand="Milla", stores=[RAHAT]),
            item(3, "Milla Süd 1l", "milla|sud|1l", stores=[BRAVO]),
        ]
        union = GuardedUnion(products)
        assert union.union(1, 2) is True
        assert union.union(2, 3) is True
        assert union.find(1) == union.find(3)

    def test_movcud_qrup_toxumu_qorunur(self):
        """Əvvəlki qaçışın qrupu itmir: eyni group_key-li məhsullar əvvəlcədən birdir."""
        products = [
            item(1, "süd", "milla|sud|1l", brand="Milla", stores=[ARAZ]),
            item(2, "Milla Süd 1l", "milla|sud|1l", stores=[BRAVO]),
        ]
        products[1]["group_key"] = products[0]["group_key"]
        union = GuardedUnion(products)
        assert union.find(1) == union.find(2)


class TestBarcode:
    def test_eyni_barkod_ferqli_marketde_avtomatik(self):
        products = [
            item(1, "süd", "milla|sud|1l", stores=[ARAZ], barcode="4760001000017"),
            item(2, "Milla Süd 1l", "milla|sud|1l", stores=[BRAVO], barcode="4760001000017"),
        ]
        found = barcode_candidates(products)
        assert [(c.a_id, c.b_id, c.similarity) for c in found] == [(1, 2, 1.0)]

    def test_eyni_marketde_barkod_cut_vermir(self):
        products = [
            item(1, "süd", "milla|sud|1l", stores=[BRAVO], barcode="4760001000017"),
            item(2, "Milla Süd 1l", "milla|sud|1l", stores=[BRAVO], barcode="4760001000017"),
        ]
        assert barcode_candidates(products) == []

    def test_bos_barkod_nezere_alinmir(self):
        products = [
            item(1, "süd", "milla|sud|1l", stores=[ARAZ], barcode=""),
            item(2, "Milla Süd 1l", "milla|sud|1l", stores=[BRAVO], barcode=None),
        ]
        assert barcode_candidates(products) == []


# ---------------------------------------------------------------- bazalı test
#
# Müvəqqəti test bazasında (conftest.py) işləyir. `verify_candidates` SAXTA
# ilə əvəz olunur: test heç vaxt Claude-u çağırmamalıdır (pul + şəbəkə), hətta
# bazada başqa testlərdən qalmış şübhəli cüt olsa belə.


@pytest.fixture
def two_market_milk():
    """Araz kataloqunda «süd [Milla] 1 l», Bravo saytında «Milla Süd 2 5% 1l»."""
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
            "VALUES (?, 'tmhash-levels', 'data/raw/tm.png', 'image')",
            (ids["araz"],),
        )
        catalog_id = cur.lastrowid
        cur.execute(
            "INSERT INTO products (canonical_key, name, brand, size_value, size_unit, group_key) "
            "VALUES ('tm|a|sud', 'süd', 'Milla', 1, 'l', 'tm|a|sud')"
        )
        araz_id = cur.lastrowid
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key) "
            "VALUES ('tm|b|sud', 'Milla Süd 2 5% 1l', 'tm|b|sud')"
        )
        bravo_id = cur.lastrowid
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price) VALUES (?, ?, ?, 2.05)",
            (araz_id, ids["araz"], catalog_id),
        )
        cur.execute(
            "INSERT INTO price_snapshots (product_id, store_id, price, source, observed_at) "
            "VALUES (?, ?, 1.89, 'site', '2026-09-11 07:00:00')",
            (bravo_id, ids["bravo"]),
        )

    yield araz_id, bravo_id

    with db_cursor() as cur:
        cur.execute("DELETE FROM price_snapshots WHERE product_id IN (?, ?)", (araz_id, bravo_id))
        cur.execute("DELETE FROM prices WHERE catalog_id = ?", (catalog_id,))
        cur.execute("DELETE FROM catalogs WHERE id = ?", (catalog_id,))
        cur.execute("DELETE FROM products WHERE id IN (?, ?)", (araz_id, bravo_id))


def _group_keys(*ids):
    with db_cursor() as cur:
        cur.execute(
            f"SELECT id, group_key FROM products WHERE id IN ({','.join('?' * len(ids))})", ids
        )
        return {r["id"]: r["group_key"] for r in cur.fetchall()}


@pytest.fixture
def no_llm(monkeypatch):
    calls = []

    def fake_verify(selected, use_cache=True):
        calls.append(len(selected))
        return [], {"checked": len(selected), "from_cache": 0, "from_llm": 0, "failed": 0, "confirmed": 0}

    monkeypatch.setattr(matcher, "verify_candidates", fake_verify)
    return calls


class TestRunMatching:
    def test_dry_run_bazani_deyismir(self, two_market_milk, no_llm):
        araz_id, bravo_id = two_market_milk
        before = _group_keys(araz_id, bravo_id)

        result = matcher.run_matching(limit=50, dry_run=True)

        assert result["dry_run"] is True
        assert {"a": "Milla süd 1 l", "b": "Milla Süd 2 5% 1l", "similarity": 1.0} in result["pairs"]
        assert _group_keys(araz_id, bravo_id) == before
        assert no_llm == []  # dry_run LLM-ə heç nə göndərmir

    def test_avtomatik_pille_qrupu_yazir(self, two_market_milk, no_llm):
        araz_id, bravo_id = two_market_milk

        matcher.run_matching(limit=50)

        keys = _group_keys(araz_id, bravo_id)
        assert keys[araz_id] == keys[bravo_id] == "tm|a|sud"

    def test_cavabda_kohne_acarlar_qalir(self, two_market_milk, no_llm):
        """`admin.js` bu açarları oxuyur — adı dəyişsə admin paneli səssizcə sınar."""
        result = matcher.run_matching(limit=50, dry_run=True)
        for key in ("pairs", "rejected", "llm", "candidates_checked", "candidates_found"):
            assert key in result
