"""
Advisor testləri — real model olmadan.

İki şeyi yoxlayırıq:
  1. FAKT bloku düzgün qurulur (bütün rəqəmlər Python-da hesablanır)
  2. astream() həqiqətən hissə-hissə qaytarır (bir dəfəyə yox)
  3. Uydurma rəqəm aşkarlanır
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.output_parsers import StrOutputParser

from ai.advisor import build_facts, verify_numbers
from ai.prompts import ADVISOR_PROMPT

COMPARE = {
    "items": [
        {
            "label": "Milla süd",
            "qty": 1,
            "prices": {"1": {"price": 1.89}, "2": {"price": 2.05}},
            "cheapest_store_id": 1,
        },
        {
            "label": "Azercay çay",
            "qty": 1,
            "prices": {"2": {"price": 3.80}},
            "cheapest_store_id": 2,
        },
    ],
    "stores": [
        {"store_id": 2, "store": "Araz", "total": 5.85, "complete": True,
         "covered": 2, "missing": [], "cheapest_count": 1, "diff": 0.0},
        {"store_id": 1, "store": "Bravo", "total": 1.89, "complete": False,
         "covered": 1, "missing": ["Azercay çay"], "cheapest_count": 1, "diff": None},
    ],
    "best": {"store_id": 2, "store": "Araz", "total": 5.85},
    "savings": None,
}


class TestBuildFacts:
    def test_mehsul_sayi_gosterilir(self):
        assert "2 məhsul" in build_facts(COMPARE)

    def test_en_ucuz_market_isarelenir(self):
        facts = build_facts(COMPARE)
        assert "ƏN UCUZ" in facts
        assert "Araz: 5.85 AZN" in facts

    def test_natamam_market_xeberdarligi_var(self):
        """Model çatışmayan məhsul barədə xəbərdarlıq yaza bilsin deyə."""
        facts = build_facts(COMPARE)
        assert "YALNIZ 1/2" in facts
        assert "çatışmır: Azercay çay" in facts

    def test_qiymet_ferqi_hesablanir(self):
        # 2.05 - 1.89 = 0.16  -> Python hesablayır, LLM yox
        assert "fərq 0.16 AZN" in build_facts(COMPARE)

    def test_tek_marketde_olan_mehsulda_ferq_yazilmir(self):
        facts = build_facts(COMPARE)
        cay_line = [line for line in facts.splitlines() if "Azercay çay:" in line][0]
        assert "fərq" not in cay_line

    def test_bos_sebet_cokmur(self):
        facts = build_facts({"items": [], "stores": [], "best": None})
        assert "0 məhsul" in facts


class TestPrompt:
    def test_faktlar_prompta_dusur(self):
        facts = build_facts(COMPARE)
        messages = ADVISOR_PROMPT.format_messages(facts=facts)
        assert "Araz: 5.85 AZN" in messages[1].content

    def test_hesablama_qadagasi_promptdadir(self):
        system = ADVISOR_PROMPT.format_messages(facts="x")[0].content
        assert "HEÇ NƏ HESABLAMA" in system


class TestStreaming:
    """astream() bütün mətni bir dəfəyə yox, hissə-hissə verməlidir."""

    def _chain(self, text: str):
        from langchain_core.messages import AIMessage

        def messages():
            yield AIMessage(content=text)

        return ADVISOR_PROMPT | GenericFakeChatModel(messages=messages()) | StrOutputParser()

    @pytest.mark.asyncio
    async def test_astream_hisse_hisse_qaytarir(self):
        chain = self._chain("Araz marketini seç. Süd Bravo-da ucuzdur.")
        chunks = [c async for c in chain.astream({"facts": "test"})]

        assert len(chunks) > 1, "cavab bir parça gəldi - streaming işləmir"
        assert "".join(chunks) == "Araz marketini seç. Süd Bravo-da ucuzdur."

    @pytest.mark.asyncio
    async def test_tek_simvol_da_axir(self):
        chain = self._chain("Bəli")
        assert "".join([c async for c in chain.astream({"facts": "test"})]) == "Bəli"


class TestSseEndpoint:
    """
    Ollama sönülü olanda istifadəçi nə görür?

    Ən pis ssenari: səhifə donub qalır və heç nə demir. Bunun qarşısını
    almaq üçün xəta SSE hadisəsi kimi göndərilir.
    """

    def test_llm_xetasi_istifadeciye_catir(self, monkeypatch):
        from fastapi.testclient import TestClient

        import app.api.basket as basket_api
        from app.db import db_cursor
        from app.main import app

        # İmza real stream_advice ilə üst-üstə düşməlidir (data, profil xülasəsi)
        async def broken(_data, _profile_summary=None):
            raise ConnectionError("Ollama əlçatmazdır")
            yield  # pragma: no cover

        monkeypatch.setattr(basket_api, "stream_advice", broken)

        with db_cursor() as cur:
            cur.execute("INSERT INTO baskets (name) VALUES ('advisor-test')")
            basket_id = cur.lastrowid
            cur.execute(
                "INSERT INTO products (canonical_key, name, category, group_key) "
                "VALUES ('adv|test', 'test məhsul', 'digər', 'adv|test')"
            )
            product_id = cur.lastrowid
            cur.execute(
                "INSERT INTO basket_items (basket_id, product_id, qty) VALUES (?, ?, 1)",
                (basket_id, product_id),
            )

        try:
            with TestClient(app) as client:
                res = client.get(f"/api/basket/advise?basket_id={basket_id}")
                assert res.status_code == 200
                assert "ConnectionError" in res.text
                assert '"type": "error"' in res.text
        finally:
            with db_cursor() as cur:
                cur.execute("DELETE FROM basket_items WHERE basket_id = ?", (basket_id,))
                cur.execute("DELETE FROM baskets WHERE id = ?", (basket_id,))
                cur.execute("DELETE FROM products WHERE canonical_key = 'adv|test'")

    def test_bos_sebet_aydin_mesaj_verir(self):
        from fastapi.testclient import TestClient

        from app.db import db_cursor
        from app.main import app

        with db_cursor() as cur:
            cur.execute("INSERT INTO baskets (name) VALUES ('advisor-empty')")
            basket_id = cur.lastrowid
        try:
            with TestClient(app) as client:
                res = client.get(f"/api/basket/advise?basket_id={basket_id}")
                assert "Səbət boşdur" in res.text
        finally:
            with db_cursor() as cur:
                cur.execute("DELETE FROM baskets WHERE id = ?", (basket_id,))


class TestVerifyNumbers:
    FACTS = build_facts(COMPARE)

    def test_faktlardaki_reqemler_qebul_edilir(self):
        text = "Araz marketini seç, cəmi 5.85 AZN. Süd Bravo-da 1.89 AZN-dir."
        assert verify_numbers(text, self.FACTS)["ok"] is True

    def test_uydurma_reqem_tutulur(self):
        text = "Araz-da cəmi 9.99 AZN olacaq."
        result = verify_numbers(text, self.FACTS)
        assert result["ok"] is False
        assert "9.99" in result["unknown_numbers"]

    def test_vergul_ve_nokte_eyni_sayilir(self):
        # Model "5,85" yaza bilər - bu, "5.85" ilə eynidir
        assert verify_numbers("Cəmi 5,85 AZN", self.FACTS)["ok"] is True

    def test_reqemsiz_metn_kecir(self):
        assert verify_numbers("Araz marketini seçmək daha yaxşıdır.", self.FACTS)["ok"] is True
