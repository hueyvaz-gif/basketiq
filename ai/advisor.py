"""
Advisor zənciri — səbət müqayisəsini insan dilində izah edir.

    faktlar (Python hesablayır) | prompt | model | StrOutputParser
                                                        ↓
                                                   astream()

ƏSAS QAYDA: LLM HEÇ NƏ HESABLAMIR.
Bütün cəmlər, fərqlər və faizlər Python-da hesablanır və modelə HAZIR şəkildə
verilir. Modelin işi yalnız bu rəqəmləri cümləyə çevirməkdir.

Niyə? Dil modelləri arifmetikada etibarsızdır. "19.65 - 16.54" sualına səhv
cavab verə bilər və istifadəçi bunu heç vaxt görməz. Rəqəmi kod hesablayanda
belə risk ümumiyyətlə yaranmır.

NİYƏ astream()?
Bu, layihədə istifadəçinin GÖZLƏDİYİ yeganə LLM çağırışıdır. Ölçdük: cavab
yazma sürəti 4.5 token/saniyədir, 4 cümlə ~100 token = ~22 saniyə.
Streaming olmasa istifadəçi 22 saniyə boş ekrana baxardı. astream() ilə isə
ilk söz 2-3 saniyəyə görünür və mətn yazılmağa davam edir.
"""

import re
from typing import AsyncIterator

from langchain_core.output_parsers import StrOutputParser

from ai.llm import get_llm
from ai.prompts import ADVISOR_PROMPT
from ai.sanitize import ReasoningFilter

# Cavabın maksimum uzunluğu. 4 cümlə üçün kifayətdir və modelin
# "danışmağa" başlamasının qarşısını alır.
ADVICE_NUM_PREDICT = 220


def build_facts(data: dict, profile_summary: str | None = None) -> str:
    """
    Müqayisə nəticəsindən modelə veriləcək FAKT bloku hazırlayır.

    Bütün rəqəmlər burada hesablanır. Model onları yalnız oxuyur.

    profile_summary: istifadəçinin profili (neçə markete gedir, büdcəsi,
    ailə ölçüsü). Model rəqəmləri dəyişmir, amma tövsiyəni ona görə qurur -
    tək markete gedən adama "iki markete get" deməsin.
    """
    lines: list[str] = []
    if profile_summary:
        lines.append(f"İSTİFADƏÇİ: {profile_summary}")
        lines.append("")
    stores = data.get("stores", [])
    items = data.get("items", [])
    best = data.get("best")

    lines.append(f"Səbətdə {len(items)} məhsul var.")
    lines.append("")
    lines.append("MARKETLƏR ÜZRƏ CƏM:")
    for store in stores:
        if store["complete"]:
            suffix = " (bütün məhsullar var)"
            if best and store["store_id"] == best["store_id"]:
                suffix += " <- ƏN UCUZ"
            elif store.get("diff"):
                suffix += f", ən ucuzdan {store['diff']:.2f} AZN baha"
        else:
            missing = ", ".join(store["missing"])
            suffix = (f" (YALNIZ {store['covered']}/{len(items)} məhsul var; "
                      f"çatışmır: {missing})")
        lines.append(f"- {store['store']}: {store['total']:.2f} AZN{suffix}")

    if data.get("savings"):
        lines.append(f"Ən ucuz və ən bahalı tam səbət arasında fərq: "
                     f"{data['savings']:.2f} AZN.")

    lines.append("")
    lines.append("MƏHSUL ÜZRƏ QİYMƏTLƏR:")
    store_names = {s["store_id"]: s["store"] for s in stores}

    for item in items:
        prices = item.get("prices", {})
        if not prices:
            lines.append(f"- {item['label']}: heç bir marketdə tapılmadı")
            continue

        parts = [f"{store_names.get(int(sid), sid)} {value['price']:.2f}"
                 for sid, value in prices.items()]
        row = f"- {item['label']}: " + ", ".join(parts)

        if len(prices) > 1:
            values = [v["price"] for v in prices.values()]
            gap = max(values) - min(values)
            cheapest = store_names.get(item.get("cheapest_store_id"), "?")
            row += f" (ən ucuz {cheapest}, fərq {gap:.2f} AZN)"
        lines.append(row)

    return "\n".join(lines)


def build_advisor_chain():
    """
    prompt | model | StrOutputParser

    Burada Pydantic parser YOXDUR - çünki nəticə struktur data deyil, mətndir.
    StrOutputParser modelin cavabından yalnız mətni çıxarır və streaming-i saxlayır.

    temperature 0 deyil (0.3): izah cümlələri tamamilə quru olmasın.
    Rəqəmlər onsuz da faktlardan gəlir, ona görə bu, risk yaratmır.
    """
    llm = get_llm(temperature=0.3, num_predict=ADVICE_NUM_PREDICT)
    return ADVISOR_PROMPT | llm | StrOutputParser()


async def stream_advice(data: dict, profile_summary: str | None = None) -> AsyncIterator[str]:
    """
    Tövsiyəni hissə-hissə (token-token) qaytarır - DÜŞÜNMƏ HİSSƏSİ ÇIXARILMIŞ.

    Filtr niyə burada, endpoint-də deyil? Çünki bu funksiya modelə çıxışın
    yeganə qapısıdır: səs interfeysi və ya başqa bir çağıran əlavə olunsa,
    filtri yenidən yazmaq lazım gəlməyəcək. Xam model mətni bu funksiyadan
    KƏNARA ÇIXMIR.

    `ReasoningFilter` axın üçündür: `<think>` etiketi iki token arasında
    bölünsə belə tutulur (bax: `ai/sanitize.py`).
    """
    chain = build_advisor_chain()
    facts = build_facts(data, profile_summary)
    reasoning_filter = ReasoningFilter()

    async for chunk in chain.astream({"facts": facts}):
        if not chunk:
            continue
        clean = reasoning_filter.feed(chunk)
        if clean:
            yield clean

    tail = reasoning_filter.flush()
    if tail:
        yield tail


# ------------------------------------------------------- hallucination yoxlaması

_NUMBER_RE = re.compile(r"\d+[.,]\d+")


def verify_numbers(text: str, facts: str) -> dict:
    """
    Modelin yazdığı hər onluq rəqəmin faktlarda mövcud olduğunu yoxlayır.

    Niyə? Prompt "hesablama" desək də, model bəzən öz-özünə rəqəm çıxarır.
    Bu yoxlama sonradan işləyir və UI-da xəbərdarlıq göstərir - yəni səhv
    gizlədilmir, görünür. LLM layihəsində şəffaflıq etibardan vacibdir.
    """
    def normalize(value: str) -> str:
        return f"{float(value.replace(',', '.')):.2f}"

    known = {normalize(m) for m in _NUMBER_RE.findall(facts)}
    used = {normalize(m) for m in _NUMBER_RE.findall(text)}
    unknown = sorted(used - known)

    return {
        "ok": not unknown,
        "unknown_numbers": unknown,
        "checked": len(used),
    }
