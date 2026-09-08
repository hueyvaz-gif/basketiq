"""
Məhsul səhifəsindəki AI qeydi — trolley-nin «rəylər» bölməsinin əvəzi.

NİYƏ RƏY YAZMIRIQ?
Trolley-də məhsulun altında müştəri rəyləri var. Bizdə istifadəçi hesabı da,
rəy cədvəli də yoxdur. Modelə «rəy yaz» demək saxta rəy istehsal etmək
deməkdir — istifadəçinin qərarına birbaşa təsir edən uydurma. Ona görə
bölmə RƏY deyil, QEYD-dir: model yalnız BİZİM hesabladığımız qiymət
faktlarını cümləyə çevirir.

ÜÇ QAT QORUYUCU (prompt tək başına kifayət etmir):
    1. FAKT BLOKU — bütün rəqəmlər Python-da hesablanır, modelə hazır verilir
       (`app/catalog.py`). Model heç nə toplamır, çıxmır, faiz almır.
    2. RƏQƏM YOXLAMASI — cavabdakı hər onluq ədəd fakt blokunda axtarılır
       (`ai.advisor.verify_numbers`). Tapılmasa qeyd GÖSTƏRİLMİR.
    3. RƏY SÖZLƏRİ SÜZGƏCİ — «dadlıdır», «tövsiyə edirəm», «alıcılar bəyənir»
       tipli ifadə görünsə qeyd GÖSTƏRİLMİR. Prompt-da qadağa var, amma
       promptun qadağası zəmanət deyil; yoxlama koddadır.

Üçünün hər biri düşəndə nəticə EYNİDİR: `available: False`. UI həmin halda
bölməni ümumiyyətlə çəkmir — nə boş kart, nə xəta mesajı. Səhifənin qalanı
(qiymət cədvəli, variantlar, oxşar məhsullar) modeldən ASILI DEYİL və
işləməyə davam edir.

KEŞ NİYƏ VACİBDİR?
Qeyd hər məhsul səhifəsində açılır. Keşsiz hər baxış bir LLM çağırışıdır -
Ollama-da 4.5 token/saniyə (ölçülüb), yəni səhifə 15-20 saniyə gözləyər.
Keş açarı fakt blokunun özüdür: qiymət dəyişəndə fakt bloku dəyişir və qeyd
avtomatik yenidən yazılır.
"""

import re

from langchain_core.output_parsers import StrOutputParser

from ai import cache
from ai.advisor import verify_numbers
from ai.llm import active_model_name, get_llm
from ai.prompts import PRODUCT_NOTE_PROMPT, PRODUCT_NOTE_PROMPT_VERSION
from ai.sanitize import strip_reasoning

# İki cümlə üçün kifayətdir. Model «danışmağa» başlasa, burada kəsilir.
NOTE_NUM_PREDICT = 140

# Modelin məhsul haqqında BİLƏ BİLMƏYƏCƏYİ iddialar.
#
# Siyahı kök üzrə qurulub, çünki Azərbaycan dilində şəkilçi sözə yapışır:
# «dadlı», «dadlıdır», «dadlıdırlar». `\b` ilə axtarsaq yalnız birincisi
# tutulardı.
BANNED_CLAIMS = (
    "dadlı",
    "ləzzət",
    "keyfiyyətli",
    "tövsiyə edir",
    "məsləhət görür",
    "bəyən",
    "sevil",
    "populyar",
    "müştəri rəy",
    "alıcılar",
    "istifadəçilər deyir",
    "ulduz",
    "reyting",
)


def build_product_facts(detail: dict) -> str:
    """
    `app/catalog.py`-nin hesabladığı datadan FAKT bloku qurur.

    Blokda yalnız BİZİM bildiyimiz şeylər var. Məhsulun tərkibi, istehsalçısı
    və ya dadı haqqında sətir YOXDUR — çünki bu məlumat bazada yoxdur, model
    isə fakt blokunda olmayan şey barədə yazmamağa təlimatlıdır.
    """
    product = detail["product"]
    offers = detail.get("offers") or []
    variants = detail.get("variants") or []

    lines = [f"MƏHSUL: {product['label']}"]
    if product.get("size"):
        lines.append(f"ÖLÇÜ: {product['size']}")
    lines.append("")

    if not offers:
        lines.append("Bu məhsulun heç bir marketdə cari qiyməti yoxdur.")
        return "\n".join(lines)

    lines.append("MARKETLƏRDƏKİ QİYMƏT:")
    for offer in offers:
        parts = [f"- {offer['store']}: {offer['price']:.2f} AZN"]
        if offer.get("old_price"):
            parts.append(
                f"(köhnə qiymət {offer['old_price']:.2f} AZN, "
                f"endirim {offer['discount_pct']:.1f}%)"
            )
        if offer.get("is_cheapest"):
            parts.append("<- ƏN UCUZ")
        lines.append(" ".join(parts))

    compare = detail.get("compare")
    if compare:
        lines.append("")
        lines.append(
            f"{compare['stores']} marketdə var. Ən ucuz ilə ən bahalı arasında "
            f"fərq: {compare['spread']:.2f} AZN."
        )
    else:
        lines.append("")
        lines.append("Yalnız bir marketdə tapılıb — müqayisə üçün ikinci qiymət yoxdur.")

    if variants:
        lines.append("")
        lines.append("ÖLÇÜ VARİANTLARI:")
        for variant in variants:
            parts = [f"- {variant['size']}: {variant['price']:.2f} AZN"]
            if variant.get("unit_price"):
                parts.append(
                    f"(1 {variant['base_unit']} = {variant['unit_price']:.2f} AZN)"
                )
            if variant.get("is_cheapest"):
                parts.append("<- ƏN UCUZ")
            if variant.get("is_best_value"):
                parts.append("<- VAHİD QİYMƏTİNƏ GÖRƏ ƏN SƏRFƏLİ")
            lines.append(" ".join(parts))

    return "\n".join(lines)


def find_banned_claim(text: str) -> str | None:
    """Mətndə uydurma rəy ifadəsi varsa onu qaytarır, yoxsa None."""
    lowered = text.lower()
    for claim in BANNED_CLAIMS:
        if claim in lowered:
            return claim
    return None


def _clean(text: str) -> str:
    """Düşünmə bloklarını atır və artıq boşluqları yığır."""
    cleaned = strip_reasoning(text)
    return re.sub(r"\s+", " ", cleaned).strip()


def product_note(detail: dict, use_cache: bool = True) -> dict:
    """
    Bir məhsul üçün AI qeydi.

    Cavab HƏMİŞƏ eyni formadadır — çağıran tərəf istisna tutmur:
        {"available": bool, "text": str, "reason": str|None,
         "cached": bool, "facts": str, "check": dict|None}

    `available=False` olanda `reason` səbəbi saxlayır. Səbəb istifadəçiyə
    GÖSTƏRİLMİR (texniki mətndir), amma jurnalda və testdə lazımdır.
    """
    facts = build_product_facts(detail)
    offers = detail.get("offers") or []
    if not offers:
        # Qiyməti olmayan məhsul üçün deyiləsi bir söz yoxdur. Modeli
        # çağırmaq onu boş yerdən cümlə uydurmağa dəvət etmək olardı.
        return {
            "available": False,
            "text": "",
            "reason": "qiymət yoxdur",
            "cached": False,
            "facts": facts,
            "check": None,
        }

    key = cache.cache_key(active_model_name(), PRODUCT_NOTE_PROMPT_VERSION, facts)
    if use_cache:
        hit = cache.get(key)
        if hit is not None:
            return {**hit, "cached": True, "facts": facts}

    try:
        chain = (
            PRODUCT_NOTE_PROMPT
            | get_llm(temperature=0.2, num_predict=NOTE_NUM_PREDICT)
            | StrOutputParser()
        )
        raw = chain.invoke({"facts": facts})
    except Exception as exc:  # şəbəkə, açar, limit - səhifə dayanmamalıdır
        return {
            "available": False,
            "text": "",
            "reason": f"model əlçatmazdır: {type(exc).__name__}",
            "cached": False,
            "facts": facts,
            "check": None,
        }

    text = _clean(raw)
    if not text:
        return {
            "available": False,
            "text": "",
            "reason": "model boş cavab verdi",
            "cached": False,
            "facts": facts,
            "check": None,
        }

    banned = find_banned_claim(text)
    if banned:
        return {
            "available": False,
            "text": "",
            "reason": f"uydurma rəy ifadəsi: «{banned}»",
            "cached": False,
            "facts": facts,
            "check": None,
        }

    check = verify_numbers(text, facts)
    if not check["ok"]:
        return {
            "available": False,
            "text": "",
            "reason": f"datada olmayan rəqəm: {check['unknown_numbers']}",
            "cached": False,
            "facts": facts,
            "check": check,
        }

    result = {"available": True, "text": text, "reason": None, "check": check}
    # YALNIZ KEÇƏN CAVAB KEŞLƏNİR: rədd edilmiş mətni saxlasaq, növbəti
    # baxışda eyni pis cavabı bir də oxuyardıq və model heç vaxt ikinci
    # şans almazdı.
    cache.put(key, result)
    return {**result, "cached": False, "facts": facts}
