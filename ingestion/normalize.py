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
