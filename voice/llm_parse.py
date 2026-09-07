"""
Səs əmrinin LLM ilə təhlili — YALNIZ regex uğursuz olanda.

Zəncir eyni LCEL şablonundadır: prompt | model | parser.

CAVAB SXEMİ QƏSDƏN QISADIR:
    {"i": "add", "q": "süd", "n": 2}

Səbəb ölçülüb: model CPU-da saniyədə 4.5 token yazır. Uzun açarlar
("intent", "query", "quantity") cavabı 2 dəfə uzadar və heç bir dəqiqlik
qazandırmaz. Eyni yanaşma `ai/chains.py`-də məhsul çıxarışında da var.
"""

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ai.llm import get_llm
from voice.commands import Command

INTENTS = "add, remove, show, compare, price, unknown"

SYSTEM = """Sən səsli alış-veriş köməkçisinin əmr təhlilçisisən.

İstifadəçinin cümləsini oxu və NİYYƏTİ təyin et. Yalnız JSON qaytar:
{{"i": "<niyyət>", "q": "<məhsul adı>", "n": <miqdar>}}

Niyyətlər:
  add     - səbətə məhsul əlavə etmək
  remove  - səbətdən çıxarmaq
  show    - səbətin siyahısı
  compare - səbət harada ucuzdur
  price   - bir məhsulun qiyməti / axtarış
  unknown - başa düşülmədi

Qaydalar:
- "q" yalnız məhsulun adıdır: ölçü, say və əmr sözü olmadan.
- "n" yoxdursa 1 yaz.
- show və compare üçün "q" boş sətir olsun.
- İZAH YAZMA, yalnız JSON."""

HUMAN = """Cümlə: {text}

JSON:"""

PROMPT = ChatPromptTemplate.from_messages([("system", SYSTEM), ("human", HUMAN)])

VALID = {"add", "remove", "show", "compare", "price", "unknown"}


def build_chain():
    # num_predict kiçikdir: cavab bir sətir JSON-dur, model "danışmağa"
    # başlasa hər əlavə token birbaşa gecikmədir.
    llm = get_llm(temperature=0.0, num_predict=60, json_mode=True)
    return PROMPT | llm | JsonOutputParser()


def parse_with_llm(text: str) -> Command | None:
    data = build_chain().invoke({"text": text})
    if not isinstance(data, dict):
        return None

    intent = str(data.get("i", "unknown")).strip().lower()
    if intent not in VALID:
        intent = "unknown"

    try:
        qty = float(data.get("n") or 1)
    except (TypeError, ValueError):
        qty = 1.0

    return Command(
        intent=intent,
        query=str(data.get("q") or "").strip(),
        qty=qty if qty > 0 else 1.0,
        raw=text,
        source="llm",
    )
