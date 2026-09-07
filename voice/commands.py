"""
Səs əmrinin mətndən niyyətə çevrilməsi.

    "səbətə iki litr süd əlavə et"  ->  add(süd, 2)
    "səbətim harada ucuzdur"        ->  compare()

NİYƏ ƏVVƏLCƏ REGEX, LLM DEYİL?
Bu, layihənin hər yerində işlədilən qaydadır: bunu kod həll edə bilirsə,
modeli çağırma. Səs əmrləri qısa və şablonludur - "əlavə et", "çıxar",
"harada ucuzdur". Onları açar sözlə tanımaq üçün model lazım deyil, üstəlik
model CPU-da saniyədə 4.5 token yazır (ölçülüb) və hər əmrə 5-10 saniyə
əlavə edərdi.

LLM yalnız regex TANIYA BİLMƏYƏNDƏ işə düşür - "yağ almaq istəyirəm, hansı
market sərfəlidir?" kimi sərbəst cümlələrdə. Bu, `parse()`-ın `use_llm`
parametridir və defolt olaraq açıqdır, amma yalnız ehtiyat yol kimi.

SİRALAMA VACİBDİR.
"səbətim harada ucuzdur" cümləsində həm "səbətim" (göstər), həm "harada ucuz"
(müqayisə) var. Qaydalar ƏN DƏQİQDƏN ƏN ÜMUMİYƏ doğru yoxlanılır, yoxsa
istifadəçi müqayisə istəyəndə səbətin siyahısını alar.
"""

import re
from dataclasses import dataclass

# Azərbaycan saylarının sözlə yazılışı - Whisper rəqəmi çox vaxt sözlə qaytarır
WORD_NUMBERS = {
    "yarım": 0.5, "bir": 1, "iki": 2, "üç": 3, "uc": 3, "dörd": 4, "dord": 4,
    "beş": 5, "bes": 5, "altı": 6, "alti": 6, "yeddi": 7, "səkkiz": 8,
    "sekkiz": 8, "doqquz": 9, "on": 10, "iyirmi": 20,
}

# Ölçü sözləri məhsul adının bir hissəsi deyil - miqdarın yanındadır
UNIT_WORDS = {
    "litr", "litrlik", "litri", "kilo", "kiloqram", "kq", "kg", "qram", "q",
    "ədəd", "eded", "dənə", "dene", "paket", "şüşə", "suse", "qutu", "banka",
}

# Əmr sözləri - məhsul adından təmizlənməlidir
COMMAND_WORDS = {
    "səbətə", "sebete", "səbətdən", "sebetden", "səbətimə", "səbətimdən",
    "səbət", "sebet", "səbətim", "sebetim", "səbətimdə", "sebetimde",
    "əlavə", "elave", "et", "at", "çıxar", "cixar", "sil", "göstər", "goster",
    "mənə", "mene", "zəhmət", "olmasa", "lütfən", "lutfen", "bir", "də", "de",
    "nə", "ne", "var", "neçəyə", "neceye", "neçədir", "qiyməti", "qiymeti",
    "qədər", "qeder", "axtar", "tap", "istəyirəm", "isteyirem", "almaq",
    "harada", "hansı", "hansi", "market", "marketdə", "marketde", "ucuz",
    "ucuzdur", "sərfəli", "serfeli", "müqayisə", "muqayise", "elə", "ele",
    # Səs mətnində qalan feillər - sorğuya düşsə axtarış heç nə tapmır
    "satılır", "satilir", "olur", "nədir", "nedir", "gətir", "getir",
}

# (niyyət, nümunə) - SIRA VACİBDİR: dəqiqdən ümumiyə
_RULES: list[tuple[str, re.Pattern]] = [
    # Müqayisə "səbətim" sözünü ehtiva edə bilər, ona görə BİRİNCİDİR
    ("compare", re.compile(
        r"(harada|hansı market|hansi market).{0,20}(ucuz|sərfəli|serfeli|al)"
        r"|müqayisə|muqayise|harada alım|harada alim|ən ucuz market|en ucuz market"
    )),
    ("remove", re.compile(r"(çıxar|cixar|sil|ləğv|legv)")),
    ("add", re.compile(r"(əlavə et|elave et|səbətə|sebete|səbətimə|sebetime)")),
    ("show", re.compile(
        r"(səbətim|sebetim|səbətdə|sebetde|səbəti göstər|sebeti goster)"
        r"|(nə var|ne var)"
    )),
    ("price", re.compile(
        r"(neçəyə|neceye|neçədir|necedir|qiyməti|qiymeti|nə qədər|ne qeder)"
        r"|(axtar|tap)"
    )),
]


@dataclass
class Command:
    intent: str                 # add | remove | show | compare | price | unknown
    query: str = ""
    qty: float = 1.0
    raw: str = ""
    source: str = "regex"       # regex | llm
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "intent": self.intent,
            "query": self.query,
            "qty": self.qty,
            "raw": self.raw,
            "source": self.source,
            "note": self.note,
        }


def normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s.,]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_qty(text: str) -> float:
    """
    Miqdarı tapır: rəqəm və ya söz.

    Yalnız ÖLÇÜ SÖZÜNÜN yanındakı say miqdar sayılır. Səbəb: "1.5 litr su"
    cümləsində "1.5" miqdardır, amma "Coca Cola 2" kimi ifadədə rəqəm
    məhsulun adının hissəsidir. Ölçü sözü olmayanda ehtiyatlı davranıb 1
    qaytarırıq - səhv miqdar səbətə səssizcə düşən xətadır.
    """
    words = text.split()
    for i, word in enumerate(words):
        if word not in UNIT_WORDS:
            continue
        if i == 0:
            continue
        previous = words[i - 1]
        if previous in WORD_NUMBERS:
            return float(WORD_NUMBERS[previous])
        number = re.fullmatch(r"\d+(?:[.,]\d+)?", previous)
        if number:
            return float(previous.replace(",", "."))
    return 1.0


def extract_query(text: str) -> str:
    """Əmr sözlərini, sayları və ölçüləri atıb məhsul adını qaytarır."""
    words = []
    for word in text.split():
        clean = word.strip(".,")
        if not clean:
            continue
        if clean in COMMAND_WORDS or clean in UNIT_WORDS or clean in WORD_NUMBERS:
            continue
        if re.fullmatch(r"\d+(?:[.,]\d+)?", clean):
            continue
        words.append(clean)
    return " ".join(words).strip()


def parse_regex(text: str) -> Command:
    """Açar sözlə niyyət tanıma. Tapılmasa intent='unknown'."""
    normalized = normalize(text)
    if not normalized:
        return Command(intent="unknown", raw=text, note="Boş mətn")

    for intent, pattern in _RULES:
        if pattern.search(normalized):
            command = Command(intent=intent, raw=text)
            if intent in ("add", "remove", "price"):
                command.query = extract_query(normalized)
                command.qty = extract_qty(normalized) if intent == "add" else 1.0
                if not command.query:
                    command.intent = "unknown"
                    command.note = "Məhsulun adı başa düşülmədi"
            return command

    return Command(intent="unknown", raw=text, note="Əmr tanınmadı")


def parse(text: str, use_llm: bool = True) -> Command:
    """
    Mətn -> əmr. Əvvəlcə regex, alınmasa LLM.

    LLM çağırışı BAHALIDIR (CPU-da bir neçə saniyə), ona görə yalnız regex
    uğursuz olanda işə düşür. Model də uğursuz olsa, istifadəçiyə nə deyə
    biləcəyini izah edirik - "başa düşmədim" cavabı faydasızdır.
    """
    command = parse_regex(text)
    if command.intent != "unknown" or not use_llm:
        return command

    try:
        from voice.llm_parse import parse_with_llm

        llm_command = parse_with_llm(text)
        if llm_command and llm_command.intent != "unknown":
            return llm_command
    except Exception as e:  # model əlçatmaz ola bilər - bu, fəlakət deyil
        command.note = f"{command.note} (LLM də cavab vermədi: {type(e).__name__})"

    return command
