"""
Matching testləri — ucuz pillə (oxşarlıq süzgəci) LLM olmadan yoxlanılır.

Bu süzgəc layihənin ən kritik "pul qoruyan" hissəsidir: səhv qurulsa,
ya hər cütü LLM-ə göndərər (saatlarla), ya da real uyğunluqları qaçırar.
"""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda

from ai.matcher import (
    Candidate,
    MatchDecision,
    UnionFind,
    _expand_match,
    find_candidates,
    key_parts,
    product_text,
    similarity,
)
from ai.prompts import MATCH_PROMPT


def product(pid, key, name, brand=None, size=None, unit=None, group=None):
    return {
        "id": pid,
        "canonical_key": key,
        "name": name,
        "brand": brand,
        "size_value": size,
        "size_unit": unit,
        "group_key": group or key,
    }


class TestKeyParts:
    def test_olcu_ayrilir(self):
        assert key_parts("milla|sud|1l") == ({"milla", "sud"}, "1l")

    def test_olcusuz_acar(self):
        assert key_parts("seker|tozu") == ({"seker", "tozu"}, "")

    def test_ondalik_olcu(self):
        assert key_parts("president|kere|yagi|0.2kg") == ({"president", "kere", "yagi"}, "0.2kg")


class TestSimilarity:
    def test_eyni_sozler_bir_verir(self):
        assert similarity("milla|sud|1l", "milla|sud|1l") == 1.0

    def test_sekilcili_form_taninir(self):
        """Azərbaycan şəkilçiləri: yağ/yağı, düyü/düyüsü, makaron/makaronu."""
        assert similarity("gunebaxan|sola|yagi|1.8l", "gunebaxan|sola|yag|1.8l") == 1.0
        assert similarity("basmati|duyu|1kg", "basmati|duyusu|1kg") == 1.0
        assert similarity("barilla|makaron|0.5kg", "barilla|makaronu|0.5kg") == 1.0

    def test_qismen_ortaq(self):
        # {yumurta} vs {toyuq, yumurtasi} -> 1+1 uyğun / 1+2 söz
        assert round(similarity("yumurta|10pcs", "toyuq|yumurtasi|10pcs"), 2) == 0.67

    def test_ortaq_soz_yoxdursa_sifir(self):
        assert similarity("sud|milla|1l", "duyu|basmati|1kg") == 0.0

    def test_qisa_sozler_qarismir(self):
        """'su' və 'süd' prefiksdir, amma FƏRQLİ məhsuldur - MIN_PREFIX bunu qoruyur."""
        assert similarity("su|sirab|1.5l", "sud|milla|1.5l") < 0.5


class TestFindCandidates:
    def test_ferqli_olculer_namized_deyil(self):
        """1 L və 2 L eyni məhsul olsa da, səbət üçün fərqlidir."""
        products = [
            product(1, "milla|sud|1l", "süd", "Milla", 1, "l"),
            product(2, "milla|sud|2l", "süd", "Milla", 2, "l"),
        ]
        assert find_candidates(products) == []

    def test_oxsar_yazilis_namized_olur(self):
        products = [
            product(1, "gunebaxan|sola|yagi|1.8l", "günəbaxan yağı", "Sola", 1.8, "l"),
            product(2, "gunebaxan|sola|yag|1.8l", "günəbaxan yağ", "Sola", 1.8, "l"),
        ]
        candidates = find_candidates(products)
        assert len(candidates) == 1
        assert candidates[0].similarity == 1.0

    def test_olcu_taninmayibsa_namized_qalir(self):
        """OCR "200 qr"-ı oxuya bilməyibsə, qərarı LLM versin - qaçırmayaq."""
        products = [
            product(1, "kere|president|yagi|0.2kg", "kərə yağı", "President", 200, "g"),
            product(2, "kere|president|yagi", "kərə yağı", "President", None, None),
        ]
        assert len(find_candidates(products)) == 1

    def test_tamamile_ferqli_mehsul_namized_deyil(self):
        products = [
            product(1, "milla|sud|1l", "süd", "Milla", 1, "l"),
            product(2, "basmati|duyu|1kg", "düyü", "Basmati", 1, "kg"),
        ]
        assert find_candidates(products) == []

    def test_artiq_eyni_qrupdadirsa_atilir(self):
        products = [
            product(1, "gunebaxan|sola|yagi|1.8l", "günəbaxan yağı", "Sola", 1.8, "l", group="g1"),
            product(2, "gunebaxan|sola|yag|1.8l", "günəbaxan yağ", "Sola", 1.8, "l", group="g1"),
        ]
        assert find_candidates(products) == []

    def test_en_oxsarlar_evvelde_gelir(self):
        products = [
            product(1, "sud|milla|1l", "süd", "Milla", 1, "l"),
            product(2, "sud|milla|icki|1l", "süd içkisi", "Milla", 1, "l"),
            product(3, "sud|1l", "süd", None, 1, "l"),
        ]
        candidates = find_candidates(products)
        assert candidates == sorted(candidates, key=lambda c: -c.similarity)


class TestProductText:
    def test_brend_ad_olcu_birlesir(self):
        p = product(1, "k", "süd", "Milla", 1, "l")
        assert product_text(p) == "Milla süd 1 l"

    def test_brend_yoxdursa_atlanir(self):
        p = product(1, "k", "yumurta", None, 10, "pcs")
        assert product_text(p) == "yumurta 10 pcs"


class TestExpandMatch:
    def test_bir_true_olur(self):
        assert _expand_match(AIMessage(content='{"s":1}')) == '{"same": true}'

    def test_sifir_false_olur(self):
        assert _expand_match(AIMessage(content='{"s":0}')) == '{"same": false}'

    def test_tam_ad_da_qebul_edilir(self):
        assert _expand_match(AIMessage(content='{"same":true}')) == '{"same": true}'

    def test_metn_kimi_gelse_de_isleyir(self):
        assert _expand_match(AIMessage(content='{"s":"1"}')) == '{"same": true}'


class TestMatchZenciri:
    def _chain(self, responses):
        parser = PydanticOutputParser(pydantic_object=MatchDecision)
        return MATCH_PROMPT | FakeListChatModel(responses=responses) | RunnableLambda(_expand_match) | parser

    def test_promptda_qosa_moterize_qalmir(self):
        system = MATCH_PROMPT.format_messages(product_a="a", product_b="b")[0].content
        assert "{{" not in system and "}}" not in system
        assert '{"s":1}' in system

    def test_eyni_qerar(self):
        result = self._chain(['{"s":1}']).invoke({"product_a": "Milla süd 1 l", "product_b": "süd Milla 1 l"})
        assert result.same is True

    def test_ferqli_qerar(self):
        result = self._chain(['{"s":0}']).invoke({"product_a": "süd", "product_b": "qatıq"})
        assert result.same is False


class TestUnionFind:
    def test_zencirvari_birlesme(self):
        """A=B və B=C təsdiqlənsə, A və C də eyni qrupda olmalıdır."""
        union = UnionFind()
        union.union(1, 2)
        union.union(2, 3)
        assert union.find(1) == union.find(3)

    def test_ayri_qruplar_qarismir(self):
        union = UnionFind()
        union.union(1, 2)
        union.union(3, 4)
        assert union.find(1) != union.find(3)
