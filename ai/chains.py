"""
LangChain LCEL zəncirləri.

ƏSAS ZƏNCİR (extraction):

    prompt  |  model  |  output parser
      ↓         ↓            ↓
   sətri    Qwen JSON   ProductAttributes
   şablona  qaytarır    (yoxlanılmış obyekt)
   qoyur

Niyə LCEL (`|`)? Çünki hər addım müstəqil dəyişdirilə bilir: modeli
dəyişmək üçün prompt-a toxunmursan, prompt-u dəyişmək üçün parser-ə.
Üstəlik hazır alınan zəncir avtomatik olaraq .invoke(), .batch(),
.astream() metodlarını qazanır - onları ayrıca yazmaq lazım gəlmir.

Niyə .batch()? 60 sətri bir-bir göndərsək, hər biri üçün ayrıca gözləyirik.
batch() onları paralel (max_concurrency qədər) göndərir.

Niyə Output Parser? Model bəzən sxemə uyğun olmayan JSON verir
(məsələn size_unit: "litr"). Parser bunu tutur və biz sətri atırıq -
verilənlər bazasına zibil düşmür.
"""

import json

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda

from ai import cache
from ai.llm import active_model_name, get_llm, message_text
from ai.prompts import COMPACT_FORMAT_INSTRUCTIONS, EXTRACTION_PROMPT, PROMPT_VERSION
from app.config import settings
from app.models import CATEGORIES, ProductAttributes

# --------------------------------------------------------------------- zəncir

attributes_parser = PydanticOutputParser(pydantic_object=ProductAttributes)

# Modelin yazdığı qısa açarlar -> bizim sxemin tam adları
_KEY_MAP = {"n": "name", "b": "brand", "v": "size_value", "u": "size_unit", "c": "category"}

# Modelin vahid üçün yaza biləcəyi variantlar -> bizim standart vahidlər.
# Niyə burada? Çünki bunu prompt ilə "yalvararaq" həll etmək olmur - kiçik model
# bəzən "L", bəzən "litr" yazır. Kodda düzəltmək həm ucuz, həm 100% etibarlıdır.
_UNIT_ALIASES = {
    "l": "l", "lt": "l", "litr": "l", "liter": "l",
    "ml": "ml", "millilitr": "ml",
    "kg": "kg", "kq": "kg", "kilo": "kg", "kiloqram": "kg",
    "g": "g", "q": "g", "qr": "g", "gr": "g", "qram": "g", "gram": "g",
    "pcs": "pcs", "eded": "pcs", "ədəd": "pcs", "pc": "pcs", "adet": "pcs",
}

# Prompt-da kateqoriyalar nömrələnmiş siyahı kimi verilir
CATEGORY_LIST_TEXT = "\n".join(f"   {i + 1} = {name}" for i, name in enumerate(CATEGORIES))


def expand_short_keys(message: BaseMessage) -> str:
    """
    {"n":"süd","b":"Milla","v":1,"u":"l","c":1}
      -> {"name":"süd","brand":"Milla","size_value":1,"size_unit":"l","category":"süd məhsulları"}

    Bu, zəncirin ortasındakı çevirmə addımıdır. Sonrakı PydanticOutputParser
    artıq tanış sxemi görür və onu yoxlayır.
    """
    data = json.loads(message_text(message))

    expanded: dict = {}
    for short, full in _KEY_MAP.items():
        # Model bəzən tam adı da yaza bilər - hər ikisini qəbul edirik
        if short in data:
            expanded[full] = data[short]
        elif full in data:
            expanded[full] = data[full]

    # Vahid: "L" / "litr" / "kq" -> "l" / "l" / "kg"
    unit = expanded.get("size_unit")
    if isinstance(unit, str):
        expanded["size_unit"] = _UNIT_ALIASES.get(unit.strip().lower())

    # Kateqoriya nömrəsi -> mətn
    category = expanded.get("category")
    if isinstance(category, bool):
        expanded["category"] = "digər"
    elif isinstance(category, (int, float)):
        index = int(category) - 1
        expanded["category"] = CATEGORIES[index] if 0 <= index < len(CATEGORIES) else "digər"
    elif isinstance(category, str) and category.isdigit():
        index = int(category) - 1
        expanded["category"] = CATEGORIES[index] if 0 <= index < len(CATEGORIES) else "digər"
    elif category not in CATEGORIES:
        expanded["category"] = "digər"

    return json.dumps(expanded, ensure_ascii=False)


def build_extraction_chain():
    """
    prompt | model | qısa açarların açılması | parser

    Layihənin AI özəyi. Dörd addımın hər biri müstəqildir:
    modeli dəyişmək üçün prompt-a, prompt-u dəyişmək üçün parser-ə toxunmursan.
    """
    prompt = EXTRACTION_PROMPT.partial(
        format_instructions=COMPACT_FORMAT_INSTRUCTIONS,
        categories=CATEGORY_LIST_TEXT,
    )
    llm = get_llm(json_mode=True)

    chain = prompt | llm | RunnableLambda(expand_short_keys) | attributes_parser

    # Model bir dəfə səhv JSON versə, bir dəfə də cəhd edirik.
    # İkinci dəfə də alınmasa - sətir atılır, pipeline dayanmır.
    return chain.with_retry(stop_after_attempt=2)


# ----------------------------------------------------------- keşli batch emalı


class ExtractionReport:
    """Emalın nəticəsi: nə alındı, nə keşdən gəldi, nə uğursuz oldu."""

    def __init__(self) -> None:
        self.results: list[ProductAttributes | None] = []
        self.from_cache = 0
        self.from_llm = 0
        self.failed = 0
        self.errors: list[str] = []

    def as_dict(self) -> dict:
        return {
            "total": len(self.results),
            "from_cache": self.from_cache,
            "from_llm": self.from_llm,
            "failed": self.failed,
            "errors": self.errors[:5],
        }


def extract_attributes(lines: list[str], use_cache: bool = True) -> ExtractionReport:
    """
    Sətir siyahısı -> ProductAttributes siyahısı (eyni sıra ilə).

    Uğursuz sətirlərin yerinə None qoyulur - sıra pozulmur ki, sonra hər
    nəticəni öz qiyməti ilə birləşdirə bilək.
    """
    report = ExtractionReport()
    report.results = [None] * len(lines)

    # Keş açarı AKTİV modelin adını daşımalıdır: Claude və Ollama fərqli
    # cavab verir, eyni açardan oxunsalar nəticələr qarışar.
    model_name = active_model_name()
    keys = [cache.cache_key(model_name, PROMPT_VERSION, line) for line in lines]

    # --- 1. Keşdən oxu ---
    pending_idx: list[int] = []
    for i, key in enumerate(keys):
        cached = cache.get(key) if use_cache else None
        if cached is None:
            pending_idx.append(i)
            continue
        try:
            report.results[i] = ProductAttributes.model_validate(cached)
            report.from_cache += 1
        except Exception:
            pending_idx.append(i)

    if not pending_idx:
        return report

    # --- 2. Qalanları LLM-ə paralel göndər ---
    chain = build_extraction_chain()
    inputs = [{"line": lines[i]} for i in pending_idx]

    outputs = chain.batch(
        inputs,
        config={"max_concurrency": settings.llm_max_concurrency},
        return_exceptions=True,   # bir sətrin xətası bütün batch-i dayandırmasın
    )

    for idx, output in zip(pending_idx, outputs):
        if isinstance(output, Exception):
            report.failed += 1
            report.errors.append(f"{lines[idx][:40]!r}: {type(output).__name__}")
            continue
        report.results[idx] = output
        report.from_llm += 1
        if use_cache:
            cache.put(keys[idx], output.model_dump())

    return report


if __name__ == "__main__":
    import sys
    import time

    test_lines = sys.argv[1:] or [
        "Süd Milla 2.5% 1L 1,89 2,45",
        "Günəbaxan yağı Sola 1.8 L 6,20",
        "Makaron Barilla 500 q 2.10",
    ]

    started = time.time()
    result = extract_attributes(test_lines, use_cache=False)
    elapsed = time.time() - started

    print(f"{elapsed:.1f} saniyə  |  {elapsed / len(test_lines):.1f} san/sətir")
    print(result.as_dict())
    for line, attrs in zip(test_lines, result.results):
        print(f"\n  {line}")
        print(f"  -> {attrs.model_dump() if attrs else 'UĞURSUZ'}")
