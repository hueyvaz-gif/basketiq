"""
LCEL zənciri testləri.

Zənciri REAL model olmadan yoxlayırıq: FakeListChatModel əvvəlcədən verilmiş
cavabları qaytarır. Beləliklə prompt -> parser -> validasiya məntiqi hər dəfə
saniyələr içində yoxlanılır, Ollama-nı gözləmədən.

Niyə vacibdir? Model bahalıdır və qeyri-determinikdir. Zəncirin "boru kəməri"
hissəsi isə determinikdir və mütləq test olunmalıdır.
"""

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda

from ai.chains import CATEGORY_LIST_TEXT, expand_short_keys
from ai.prompts import COMPACT_FORMAT_INSTRUCTIONS, EXTRACTION_PROMPT
from app.models import ProductAttributes
from ingestion.pipeline import build_products


def fake_chain(responses: list[str]):
    """Real zəncirin eynisi, yalnız model saxtadır."""
    prompt = EXTRACTION_PROMPT.partial(
        format_instructions=COMPACT_FORMAT_INSTRUCTIONS,
        categories=CATEGORY_LIST_TEXT,
    )
    parser = PydanticOutputParser(pydantic_object=ProductAttributes)
    return prompt | FakeListChatModel(responses=responses) | RunnableLambda(expand_short_keys) | parser


class TestPromptQurulusu:
    def test_promptda_qosa_moterize_qalmir(self):
        """.partial() dəyəri şablon kimi oxumur - {{ }} yazsaq modelə hərfi düşər."""
        prompt = EXTRACTION_PROMPT.partial(
            format_instructions=COMPACT_FORMAT_INSTRUCTIONS,
            categories=CATEGORY_LIST_TEXT,
        )
        system = prompt.format_messages(line="test")[0].content
        assert "{{" not in system and "}}" not in system

    def test_kateqoriyalar_nomrelenib(self):
        assert "1 = süd məhsulları" in CATEGORY_LIST_TEXT
        assert "10 = digər" in CATEGORY_LIST_TEXT


class TestExpandShortKeys:
    def _expand(self, raw: str) -> dict:
        from langchain_core.messages import AIMessage

        return json.loads(expand_short_keys(AIMessage(content=raw)))

    def test_qisa_acarlar_acilir(self):
        out = self._expand('{"n":"süd","b":"Milla","v":1,"u":"l","c":1}')
        assert out == {
            "name": "süd", "brand": "Milla", "size_value": 1,
            "size_unit": "l", "category": "süd məhsulları",
        }

    def test_tam_acarlar_da_qebul_edilir(self):
        out = self._expand('{"name":"düyü","size_value":1,"size_unit":"kg","category":8}')
        assert out["name"] == "düyü"
        assert out["category"] == "quru ərzaq"

    def test_boyuk_herfli_vahid_duzelir(self):
        # Model tez-tez "L" yazır - bu, Literal validasiyasını sındırırdı
        assert self._expand('{"n":"su","u":"L","v":1.5,"c":5}')["size_unit"] == "l"

    def test_azerbaycanca_vahid_duzelir(self):
        assert self._expand('{"n":"düyü","u":"kq","v":1,"c":8}')["size_unit"] == "kg"
        assert self._expand('{"n":"un","u":"qram","v":500,"c":8}')["size_unit"] == "g"

    def test_taninmayan_vahid_none_olur(self):
        assert self._expand('{"n":"yumurta","u":"qutu","v":10,"c":10}')["size_unit"] is None

    def test_kateqoriya_nomresi_araliqdan_kenardirsa_diger(self):
        assert self._expand('{"n":"x","c":99}')["category"] == "digər"

    def test_kateqoriya_metn_kimi_gelse_de_isleyir(self):
        assert self._expand('{"n":"x","c":"3"}')["category"] == "ət və balıq"


class TestZencirUcdanUca:
    def test_duzgun_cavab_obyekte_cevrilir(self):
        chain = fake_chain(['{"n":"süd","b":"Milla","v":1,"u":"l","c":1}'])
        result = chain.invoke({"line": "Süd Milla 1L 1,89"})

        assert isinstance(result, ProductAttributes)
        assert result.name == "süd"
        assert result.brand == "Milla"
        assert result.size_unit == "l"
        assert result.category == "süd məhsulları"

    def test_batch_sirani_qoruyur(self):
        chain = fake_chain([
            '{"n":"süd","b":"Milla","v":1,"u":"l","c":1}',
            '{"n":"düyü","b":null,"v":1,"u":"kg","c":8}',
        ])
        results = chain.batch([{"line": "a"}, {"line": "b"}])
        assert [r.name for r in results] == ["süd", "düyü"]

    def test_agilsiz_olcu_reddedilir(self):
        chain = fake_chain(['{"n":"süd","v":999999,"u":"l","c":1}'])
        with pytest.raises(Exception):
            chain.invoke({"line": "test"})

    def test_pozuq_json_reddedilir(self):
        chain = fake_chain(["bu JSON deyil"])
        with pytest.raises(Exception):
            chain.invoke({"line": "test"})


class TestBuildProducts:
    """LLM atributları + regex qiyməti -> yekun məhsul."""

    def _line(self, text, price, old=None):
        from ingestion.cleaner import CleanLine

        return CleanLine(raw=text, text=text, prices=[price], price=price, old_price=old)

    def test_qiymet_regexden_gelir_llmden_yox(self):
        line = self._line("Süd Milla 1L 1,89", 1.89)
        attrs = ProductAttributes(name="süd", brand="Milla", size_value=1, size_unit="l",
                                  category="süd məhsulları")
        products, skipped = build_products([line], [attrs])

        assert skipped == 0
        assert products[0].price == 1.89
        assert products[0].unit_price == 1.89
        assert products[0].canonical_key == "milla|sud|1l"

    def test_llm_ugursuz_olsa_setir_oturulur(self):
        line = self._line("Süd 1,89", 1.89)
        products, skipped = build_products([line], [None])
        assert products == [] and skipped == 1

    def test_bos_ad_mehsul_sayilmir(self):
        # Model reklam sətrini tanıyıb "" qaytarır
        line = self._line("Endirimlər 12 mart 2,00", 2.00)
        attrs = ProductAttributes(name="", category="digər")
        products, skipped = build_products([line], [attrs])
        assert products == [] and skipped == 1

    def test_qiymet_yoxdursa_mehsul_yazilmir(self):
        from ingestion.cleaner import CleanLine

        line = CleanLine(raw="Süd Milla", text="Süd Milla", prices=[], price=None)
        attrs = ProductAttributes(name="süd", category="süd məhsulları")
        products, skipped = build_products([line], [attrs])
        assert products == [] and skipped == 1
