"""
Normalizasiya: ölçü vahidləri, vahid qiymət və canonical_key.

Bu faylda LLM YOXDUR - hamısı deterministik koddur.

NİYƏ VACİBDİR:
"1.89 AZN / 1.5 L" və "1.40 AZN / 1 L" - hansı ucuzdur? İnsan gözü səhv edir.
Ona görə hər məhsul üçün 1 kq / 1 L qiymətini hesablayırıq və bütün müqayisəni
onun üzərində qururuq.

canonical_key isə fərqli marketlərdəki eyni məhsulu birləşdirən açardır:
  "MILLA süd 1 lt 2,5%"  -> milla|sud|1l
  "Süd Milla 2.5% 1L"    -> milla|sud|1l
Beləliklə sətirlərin 90%-i LLM-siz uyğunlaşdırılır - LLM yalnız şübhəli
qalan hallara xərclənir (Həftə 2-nin ikinci hissəsi).
"""

import re
import unicodedata

# Vahidlər əsas vahidə çevrilir: kq, litr, ədəd
_TO_BASE = {
    "kg": (1.0, "kg"),
    "g": (0.001, "kg"),
    "l": (1.0, "l"),
    "ml": (0.001, "l"),
    "pcs": (1.0, "pcs"),
}

_AZ_TRANSLIT = str.maketrans(
    "əöüğışçİĞÜŞÖÇƏI",
    "eougiscIGUSOCEI",
)

# Açarda əhəmiyyəti olmayan sözlər
_STOPWORDS = {"ve", "and", "the", "az", "kq", "kg", "gr", "g", "ml", "l", "lt", "litr", "eded", "pcs"}


def to_base(size_value: float | None, size_unit: str | None) -> tuple[float | None, str | None]:
    """(500, 'g') -> (0.5, 'kg').  Vahid tanınmırsa (None, None)."""
    if size_value is None or size_unit is None:
        return None, None
    factor_unit = _TO_BASE.get(size_unit.lower())
    if not factor_unit:
        return None, None
    factor, base = factor_unit
    return round(size_value * factor, 6), base


def unit_price(price: float, size_value: float | None, size_unit: str | None) -> tuple[float | None, str | None]:
    """
    1 kq / 1 L / 1 ədəd qiymətini hesablayır.

    Ölçü bilinmirsə None qaytarır - UI-da "—" göstərilir.
    Uydurmaq YOX: bilinməyən dəyər gizlədilməməlidir.
    """
    qty, base = to_base(size_value, size_unit)
    if not qty or qty <= 0 or base is None:
        return None, None
    return round(price / qty, 2), base


def slug_token(text: str) -> str:
    """Azərbaycan hərflərini sadələşdirir və yalnız hərf/rəqəm saxlayır."""
    text = text.lower().translate(_AZ_TRANSLIT)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", text)


def size_token(size_value: float | None, size_unit: str | None) -> str:
    """(1.5, 'l') -> '1.5l'. Ölçü yoxdursa boş sətir."""
    qty, base = to_base(size_value, size_unit)
    if qty is None or base is None:
        return ""
    # 1.0 -> "1",  0.5 -> "0.5"
    text = f"{qty:.3f}".rstrip("0").rstrip(".")
    return f"{text}{base}"


def canonical_key(
    name: str,
    brand: str | None,
    size_value: float | None,
    size_unit: str | None,
) -> str:
    """
    Eyni məhsulun fərqli yazılışlarını eyni açara gətirir.

    Sözlər ƏLİFBA SIRASI ilə düzülür ki, "Süd Milla" və "Milla süd"
    eyni nəticəni versin.
    """
    words = []
    for part in (brand or "", name or ""):
        for token in re.split(r"[\s/\\-]+", part):
            slug = slug_token(token)
            if slug and slug not in _STOPWORDS and not slug.isdigit():
                words.append(slug)

    unique_sorted = sorted(set(words))
    key = "|".join(unique_sorted)

    size = size_token(size_value, size_unit)
    if size:
        key = f"{key}|{size}" if key else size

    return key or "namelum"


# ------------------------------------------------------------- uyğunlaşdırma açarı
#
# NİYƏ canonical_key KİFAYƏT ETMİR? (ölçüldü, 2026-09-11)
# Bravo (Wolt) ölçünü çox vaxt ayrıca sətirdə yox, ADIN İÇİNDƏ yazır:
#     «Milla Qatıq 1.5% 450qr»  ->  canonical_key = 450qr|milla|qatiq
# «450qr» ölçü kimi yox, adi söz kimi açara düşür və Arazın
# `azersud|qatiq|0.45kg` tipli açarı ilə HEÇ VAXT üst-üstə düşmür.
# 13 168 Bravo məhsulundan cəmi 855-inin ölçüsü tanınırdı; addan oxuyanda 8 911.
#
# NİYƏ canonical_key-i DÜZƏLTMİRİK? O, `products` cədvəlində UNIQUE-dir və
# mağaza çəkilişi məhsulu məhz onunla tapır. Hesablanma qaydası dəyişsə,
# növbəti çəkiliş ~13 min YENİ sətir yaradardı: qiymət tarixçəsi ikiyə
# bölünər, səbətdəki məhsullar köhnə sətirdə qalardı. Ona görə uyğunlaşdırma
# üçün AYRICA açar hesablanır, köhnəsinə toxunulmur.

# «450qr», «1kq», «10 L», «75ml», «10əd.», «(6əd.)», «1,5 litr»
# `(?<![\w.,])` — «11x8sm»-dəki «8» və «2x100qr»-dakı «100» ölçü sayılmasın:
# rəqəmdən əvvəl hərf varsa, bu, ölçü deyil (çoxluq və ya ölçü-ölçü yazısıdır).
_NAME_SIZE_RE = re.compile(
    r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*"
    r"(kq|kg|qr|gr|ml|litr|lt|ədəd|eded|əd|ed|pcs|q|g|l)\.?(?!\w)",
    re.IGNORECASE,
)
_NAME_UNITS = {
    "kq": "kg", "kg": "kg",
    "qr": "g", "gr": "g", "q": "g", "g": "g",
    "ml": "ml", "litr": "l", "lt": "l", "l": "l",
    "ədəd": "pcs", "eded": "pcs", "əd": "pcs", "ed": "pcs", "pcs": "pcs",
}

# Yağlılıq: «2.5%», «3,2 %», «45%» və Wolt-un vergülü itirdiyi «2 5%».
_FAT_RE = re.compile(r"(?<![\w.,])(\d{1,2})(?:[.,]|\s)?(\d)?\s*%")


def size_from_name(name: str | None) -> tuple[float | None, str | None]:
    """
    «Milla Qatıq 1.5% 450qr» -> (450.0, 'g').  Ölçü yoxdursa (None, None).

    Bir neçə uyğunluq varsa SONUNCU götürülür: ölçü adətən adın sonundadır,
    əvvəlindəki rəqəmlər isə çox vaxt model adıdır («7days», «Fairy 2»).
    """
    matches = list(_NAME_SIZE_RE.finditer(name or ""))
    if not matches:
        return None, None
    value, unit = matches[-1].groups()
    return float(value.replace(",", ".")), _NAME_UNITS[unit.lower()]


def fat_percent(name: str | None) -> float | None:
    """
    «Milla Süd 2 5% 1l» -> 2.5.  Faiz yoxdursa None.

    NİYƏ LAZIMDIR? canonical_key rəqəmləri atır, yəni 2.5% və 3.2% süd eyni
    açara düşür. Bunlar FƏRQLİ məhsuldur (qiyməti də fərqlidir). Faiz açara
    yazılmır — ölçü kimi ZİDDİYYƏT şərtidir: hər ikisində varsa və fərqlidirsə,
    cüt birləşdirilmir.
    """
    matches = list(_FAT_RE.finditer(name or ""))
    if not matches:
        return None
    whole, fraction = matches[-1].groups()
    value = float(f"{whole}.{fraction}" if fraction else whole)
    return value if 0 < value <= 100 else None


def brand_from_name(name: str | None, known_brands: set[str]) -> str | None:
    """
    Addakı brendi TANINMIŞ brendlər siyahısına görə tapır. Nəticə slug-dır.

        «Uzun Ömür İvanovka Qatıq 700qr», {"ivanovka"}  -> "ivanovka"
        «Zeytun Bağları Zeytun Yağı 1l», {"zeytunbaglari"} -> "zeytunbaglari"

    NİYƏ SİYAHI, «ilk söz» YOX? Bravo kartında brend sahəsi YOXDUR və ilk
    söz çox vaxt brend deyil («Uzun Ömür ...», «Kənd ...»). Siyahı kataloqlardan
    gəlir (Araz/Rahat-da brend ayrıca yazılır). Bu, həqiqət yox, BLOKLAMA
    açarıdır: səhv brend ən pis halda cütü LLM-ə göndərir, birləşdirmir.

    Çoxsözlü brendlər («Zeytun Bağları», «7 Days») üçün yan-yana sözlər də
    birləşdirilib yoxlanılır; ən uzun uyğunluq üstündür.
    """
    tokens = [slug_token(t) for t in re.split(r"[\s/\\()-]+", name or "")]
    tokens = [t for t in tokens if t]
    for width in (3, 2, 1):
        for start in range(len(tokens) - width + 1):
            candidate = "".join(tokens[start:start + width])
            if candidate in known_brands:
                return candidate
    return None


def match_key(
    name: str,
    brand: str | None,
    size_value: float | None,
    size_unit: str | None,
) -> str:
    """
    Uyğunlaşdırma açarı: canonical_key ilə eyni forma, amma ölçü addan da oxunur.

        Bravo  ("Milla Süd 2 5% 1l", None, None, None) -> milla|sud|1l
        Araz   ("süd", "Milla", 1.0, "l")             -> milla|sud|1l

    Ayrıca sahədəki ölçü ÜSTÜNDÜR: o, kartın/kataloqun strukturlu hissəsindən
    gəlir, addakı isə mətndir. Ölçü və faiz sözləri addan silinir ki, açara
    «450qr» kimi söz düşməsin.
    """
    if not size_token(size_value, size_unit):
        size_value, size_unit = size_from_name(name)
    words = _FAT_RE.sub(" ", _NAME_SIZE_RE.sub(" ", name or ""))
    return canonical_key(words, brand, size_value, size_unit)


def display_label(name: str, brand: str | None) -> str:
    """
    "barilla" + "barilla makaronu" -> "barilla makaronu"

    LLM bəzən brendi həm brand, həm name sahəsinə yazır. Bunu prompt ilə
    tam həll etmək mümkün olmadı; UI-da təkrar görünməsin deyə burada kəsirik.
    """
    name = (name or "").strip()
    brand = (brand or "").strip()
    if not brand:
        return name
    if slug_token(brand) and slug_token(brand) in slug_token(name):
        return name
    return f"{brand} {name}".strip()


def display_size(size_value, size_unit) -> str:
    """
    (1.0, 'l') -> "1 l",  (0.5, 'kg') -> "0.5 kg",  (None, ...) -> ""

    Niyə ayrıca funksiya? Bazada `size_value` REAL tipdədir, yəni 1 rəqəmi
    "1.0" kimi qayıdır. Ekranda "1000.0 g" yazmaq səliqəsizdir. Bu formatlama
    əvvəllər üç ayrı yerdə təkrarlanırdı və biri (səbət cədvəli) unudulmuşdu -
    ona görə bir yerə yığıldı.
    """
    if not size_value or not size_unit:
        return ""
    try:
        value = float(size_value)
    except (TypeError, ValueError):
        return ""
    number = int(value) if value.is_integer() else value
    return f"{number} {size_unit}"
