"""
Uyğunlaşdırma qərarları (ADDIM 4b) — `match_decisions` cədvəli.

Bu testlər üç vədi kilidləyir:
  1. insanın «xeyr, ayrıdır» dediyi cüt növbəti qaçışda YENƏ birləşmir;
  2. LLM bir cütü ikinci dəfə soruşulmur (pul + vaxt);
  3. `group_key` qərarlardan qurulur - qərar dəyişəndə qrup da dəyişir.

LLM həmişə SAXTADIR: test heç vaxt Claude-u çağırmamalıdır.
"""

import sqlite3

import pytest

from ai import matcher
from ai.matcher import GuardedUnion, decide, load_decisions, record_decisions
from app.db import SCHEMA, _migrate_match_decisions, db_cursor

BRAVO, ARAZ, RAHAT = 2, 15, 1266


def item(pid, key, stores, group=None):
    return {
        "id": pid,
        "canonical_key": f"ck{pid}",
        "match_key": key,
        "name": key,
        "brand": None,
        "size_value": None,
        "size_unit": None,
        "group_key": group or f"ck{pid}",
        "stores": set(stores),
    }


class TestGuardedUnionQadaga:
    def test_ferqlidir_qerari_kecisli_birlesmeni_de_dayandirir(self):
        """İnsan «1 ≠ 3» deyib: 1=2 və 2=3 təsdiqlənsə belə, 3 qrupa girmir."""
        products = [
            item(1, "milla|sud|1l", [ARAZ]),
            item(2, "milla|sud|1l", [RAHAT]),
            item(3, "milla|sud|1l", [BRAVO]),
        ]
        union = GuardedUnion(products, forbidden={(1, 3)})
        assert union.union(1, 2) is True
        assert union.union(2, 3) is False
        assert union.find(1) != union.find(3)

    def test_toxum_sondurulende_kohne_qrup_nezere_alinmir(self):
        products = [item(1, "a|1l", [ARAZ], group="g"), item(2, "a|1l", [BRAVO], group="g")]
        assert GuardedUnion(products).find(1) == GuardedUnion(products).find(2)
        union = GuardedUnion(products, seed=False)
        assert union.find(1) != union.find(2)


class TestKohneQruplarinKocurulmesi:
    """Cədvəl yarananda əvvəlki qaçışların qrupları itməməlidir."""

    @staticmethod
    def fresh_db():
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO products (canonical_key, name, group_key) "
            "VALUES ('a', 'a', 'g'), ('b', 'b', 'g'), ('c', 'c', 'c')"
        )
        return conn

    def test_kohne_qrup_legacy_qerarina_cevrilir(self):
        conn = self.fresh_db()
        _migrate_match_decisions(conn)
        rows = [tuple(r) for r in conn.execute("SELECT a_id, b_id, decision, source FROM match_decisions")]
        assert rows == [(1, 2, "same", "legacy")]

    def test_ikinci_cagiris_tekrar_kocurmur(self):
        conn = self.fresh_db()
        _migrate_match_decisions(conn)
        _migrate_match_decisions(conn)
        assert conn.execute("SELECT COUNT(*) FROM match_decisions").fetchone()[0] == 1


# ---------------------------------------------------------------- bazalı testlər


@pytest.fixture
def pairs():
    """
    İki cüt, Araz kataloqu ⇄ Bravo rəfi:
      düyü  — ölçü iki tərəfdə var, bal 0.86 -> LLM-ə gedir
      ayran — kataloqda ölçü YOXDUR       -> insana gedir (pending)
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
            "VALUES (?, 'tdhash-decisions', 'data/raw/td.png', 'image')",
            (ids["araz"],),
        )
        catalog_id = cur.lastrowid
        made = {}
        for tag, key, name, brand, size, unit, store in (
            ("rice_a", "td|a|duyu", "basmati düyü", "Sultan", 1, "kg", "araz"),
            ("rice_b", "td|b|duyu", "Sultan Basmati Düyü Uzun 1kq", None, None, None, "bravo"),
            ("ayran_a", "td|a|ayran", "ayran", "Azərsüd", None, None, "araz"),
            ("ayran_b", "td|b|ayran", "Azərsüd Ayran 1l", None, None, None, "bravo"),
        ):
            cur.execute(
                "INSERT INTO products (canonical_key, name, brand, size_value, size_unit, group_key) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key, name, brand, size, unit, key),
            )
            made[tag] = cur.lastrowid
            if store == "araz":
                cur.execute(
                    "INSERT INTO prices (product_id, store_id, catalog_id, price) VALUES (?, ?, ?, 3.0)",
                    (made[tag], ids["araz"], catalog_id),
                )
            else:
                cur.execute(
                    "INSERT INTO price_snapshots (product_id, store_id, price, source, observed_at) "
                    "VALUES (?, ?, 2.9, 'site', '2026-09-11 07:00:00')",
                    (made[tag], ids["bravo"]),
                )

    yield made

    with db_cursor() as cur:
        marks = ",".join("?" * len(made))
        cur.execute(f"DELETE FROM price_snapshots WHERE product_id IN ({marks})", list(made.values()))
        cur.execute("DELETE FROM prices WHERE catalog_id = ?", (catalog_id,))
        cur.execute("DELETE FROM catalogs WHERE id = ?", (catalog_id,))
        # match_decisions ON DELETE CASCADE ilə özü gedir
        cur.execute(f"DELETE FROM products WHERE id IN ({marks})", list(made.values()))


@pytest.fixture
def llm_says_yes(monkeypatch):
    """Saxta LLM: göndərilən hər cütə «bəli» deyir və neçə cüt gəldiyini sayır."""
    calls = []

    def fake_verify(selected, use_cache=True):
        calls.append(len(selected))
        stats = {"checked": len(selected), "from_cache": 0, "from_llm": len(selected),
                 "failed": 0, "confirmed": len(selected)}
        return list(selected), stats

    monkeypatch.setattr(matcher, "verify_candidates", fake_verify)
    return calls


def _pair(a, b):
    return (a, b) if a < b else (b, a)


def _group(pid):
    with db_cursor() as cur:
        cur.execute("SELECT group_key FROM products WHERE id = ?", (pid,))
        return cur.fetchone()["group_key"]


class TestQerarYaddasi:
    def test_llm_cutu_ikinci_defe_sorusulmur(self, pairs, llm_says_yes):
        matcher.run_matching(limit=50)
        matcher.run_matching(limit=50)

        assert llm_says_yes[0] >= 1
        assert llm_says_yes[1] == 0, "artıq cavablanmış cüt LLM-ə yenidən getdi"
        decision = load_decisions()[_pair(pairs["rice_a"], pairs["rice_b"])]
        assert (decision["decision"], decision["source"]) == ("same", "llm")
        assert _group(pairs["rice_a"]) == _group(pairs["rice_b"])

    def test_olcusuz_cut_insani_gozleyir(self, pairs, llm_says_yes):
        matcher.run_matching(limit=50)

        decision = load_decisions()[_pair(pairs["ayran_a"], pairs["ayran_b"])]
        assert decision["decision"] == "pending"
        assert decision["reason"] == "ölçü bilinmir"
        assert _group(pairs["ayran_a"]) != _group(pairs["ayran_b"])

    def test_insanin_xeyr_qerari_qrupu_dagidir_ve_qalir(self, pairs, llm_says_yes):
        matcher.run_matching(limit=50)
        assert _group(pairs["rice_a"]) == _group(pairs["rice_b"])

        decide(pairs["rice_a"], pairs["rice_b"], same=False)
        assert _group(pairs["rice_a"]) != _group(pairs["rice_b"])

        # Növbəti maşın qaçışı insan qərarını dəyişmir
        matcher.run_matching(limit=50)
        decision = load_decisions()[_pair(pairs["rice_a"], pairs["rice_b"])]
        assert (decision["decision"], decision["source"]) == ("different", "human")
        assert _group(pairs["rice_a"]) != _group(pairs["rice_b"])

    def test_insanin_beli_qerari_birlesdirir(self, pairs, llm_says_yes):
        matcher.run_matching(limit=50)
        decide(pairs["ayran_a"], pairs["ayran_b"], same=True)

        assert _group(pairs["ayran_a"]) == _group(pairs["ayran_b"])
        decision = load_decisions()[_pair(pairs["ayran_a"], pairs["ayran_b"])]
        assert (decision["decision"], decision["source"]) == ("same", "human")

    def test_masin_insan_qerarinin_ustune_yazmir(self, pairs, llm_says_yes):
        decide(pairs["rice_a"], pairs["rice_b"], same=False)
        record_decisions([{
            "a_id": pairs["rice_a"], "b_id": pairs["rice_b"], "decision": "same",
            "source": "llm", "similarity": 0.86, "reason": None,
        }])
        decision = load_decisions()[_pair(pairs["rice_a"], pairs["rice_b"])]
        assert (decision["decision"], decision["source"]) == ("different", "human")
