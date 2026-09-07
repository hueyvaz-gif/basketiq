"""
OCR/pypdf çıxışının təmizlənməsi.

NİYƏ BU FAYL VACİBDİR:
Bir kataloq səhifəsindən 200-300 sətir çıxır, amma onların yalnız ~20%-i məhsuldur.
Qalanı: reklam şüarları, telefon nömrələri, tarixlər, OCR zibili.

Əgər hamısını LLM-ə göndərsək:
  - GPU-suz maşında saatlarla işləyər,
  - model zibil sətirlərdən "məhsul uydurmağa" başlayar.

Ona görə burada ucuz və deterministik qaydalarla süzürük.
Qiyməti də burada regex ilə çıxarırıq - bu, LLM-in işini üçdə birinə salır.
"""

import re
from dataclasses import dataclass, field

# 1.89 / 1,89 / 12 , 50  -> onluq qiymət
_PRICE_DECIMAL = re.compile(r"(?<![\d.,])(\d{1,4})\s*[.,]\s*(\d{2})(?![\d])")
# 5 AZN / 5₼ / 5 man -> tam qiymət (valyuta işarəsi məcburidir, yoxsa hər rəqəm qiymət olardı)
_PRICE_INTEGER = re.compile(r"(?<![\d.,])(\d{1,4})\s*(?:AZN|azn|Azn|₼|man\.?)(?![\w])")

# OCR-in ən çox səhv saldığı hərflər
_OCR_DIGIT_MAP = {"O": "0", "o": "0", "l": "1", "I": "1", "|": "1", "S": "5", "B": "8"}

# Rəqəmdən SONRA gəlib söz sonunda dayanan hərflər üçün ayrıca, daha dar siyahı.
# 'l' və 'I' bura DAXİL DEYİL, çünki "1,5l" = 1.5 litr deməkdir - onu "1,51"-ə
# çevirmək qiyməti tamamilə korlayardı.
_OCR_TRAILING_MAP = {"O": "0", "o": "0", "S": "5", "B": "8"}

# Bu sözlər olan və qiyməti olmayan sətirlər məhsul deyil
_NOISE_KEYWORDS = {
    "endirim", "endirimler", "endirimlər", "aksiya", "kampaniya", "kampanya",
    "www", "http", "instagram", "facebook", "tiktok", "whatsapp",
    "hörmətli", "musteri", "müştəri", "qiymətlər", "kataloq", "katalog",
    "etibarlidir", "etibarlıdır", "tarixe", "tarixə", "qeder", "qədər",
    "filial", "unvan", "ünvan", "telefon", "elaqe", "əlaqə", "call center",
    "скидка", "акция", "каталог", "discount",
}

# Ağlabatan qiymət aralığı - bundan kənar rəqəm OCR səhvidir
MIN_PRICE = 0.05
MAX_PRICE = 999.0


@dataclass
class CleanLine:
    """Təmizlənmiş bir sətir."""

    raw: str                              # OCR-dan gələn orijinal (şəffaflıq üçün saxlanılır)
    text: str                             # normallaşdırılmış
    prices: list[float] = field(default_factory=list)
    price: float | None = None            # cari (endirimli) qiymət
    old_price: float | None = None        # köhnə qiymət (varsa)

    def to_dict(self) -> dict:
        return {
            "raw": self.raw,
            "text": self.text,
            "price": self.price,
            "old_price": self.old_price,
            "prices": self.prices,
        }


@dataclass
class CleanResult:
    lines: list[CleanLine]
    stats: dict


# ------------------------------------------------------------------ addımlar


def normalize(line: str) -> str:
    """Artıq boşluqlar, görünməz simvollar və təkrar durğu işarələri təmizlənir."""
    line = line.replace(" ", " ").replace("﻿", "")
    line = re.sub(r"[^\S\n]+", " ", line)          # bütün boşluq növləri -> tək boşluq
    line = re.sub(r"[·•●▪→»]+", " ", line)          # kataloq bəzək simvolları
    line = re.sub(r"\s*([.,])\s*(?=\d{2}\b)", r"\1", line)  # "1 , 89" -> "1,89"
    return line.strip()


def fix_ocr_digits(line: str) -> str:
    """
    'l,89' -> '1,89'. Yalnız hərfin bir tərəfi rəqəm/vergüldürsə düzəldirik ki,
    adi sözlərə toxunmayaq ("Sola" -> "5ola" olmasın).
    """
    chars = list(line)
    for i, ch in enumerate(chars):
        if ch not in _OCR_DIGIT_MAP:
            continue
        prev_c = chars[i - 1] if i > 0 else ""
        next_c = chars[i + 1] if i + 1 < len(chars) else ""
        prev_ok = prev_c.isdigit() or prev_c in ".,"
        next_ok = next_c.isdigit() or next_c in ".,"

        if prev_ok and next_ok:
            # Hər iki tərəf rəqəm -> tam əminik
            chars[i] = _OCR_DIGIT_MAP[ch]
        elif prev_ok and not next_c.isalpha() and ch in _OCR_TRAILING_MAP:
            # "1,8O AZN" -> "1,80 AZN" (amma "1,5l" toxunulmaz qalır)
            chars[i] = _OCR_TRAILING_MAP[ch]
    return "".join(chars)


def extract_prices(line: str) -> list[float]:
    """Sətirdəki bütün ağlabatan qiymətləri tapır."""
    found: list[float] = []

    for whole, cents in _PRICE_DECIMAL.findall(line):
        try:
            found.append(float(f"{whole}.{cents}"))
        except ValueError:
            continue

    for whole in _PRICE_INTEGER.findall(line):
        try:
            found.append(float(whole))
        except ValueError:
            continue

    result = sorted({p for p in found if MIN_PRICE <= p <= MAX_PRICE})
    return result


def is_noise(text: str, prices: list[float]) -> str | None:
    """Sətir atılmalıdırsa səbəbi qaytarır, saxlanmalıdırsa None."""
    if len(text) < 4:
        return "cox_qisa"

    letters = sum(c.isalpha() for c in text)
    if letters < 2:
        return "herfsiz"

    if not prices:
        return "qiymetsiz"

    # Simvol zibili: hərf+rəqəm nisbəti çox aşağıdırsa OCR səhvidir
    useful = sum(c.isalnum() or c.isspace() for c in text)
    if useful / len(text) < 0.6:
        return "simvol_zibili"

    low = text.lower()
    if any(kw in low for kw in _NOISE_KEYWORDS) and letters > 3 * len(prices):
        return "reklam_metni"

    return None


def split_prices(prices: list[float]) -> tuple[float | None, float | None]:
    """
    Cari və köhnə qiyməti ayırır.

    Heuristika: kataloqda ən kiçik rəqəm adətən endirimli qiymətdir.
    Bu, 100% dəqiq deyil - Həftə 2-də LLM bunu yoxlayacaq. Amma sətirlərin
    böyük hissəsini LLM-siz həll edir.
    """
    if not prices:
        return None, None
    if len(prices) == 1:
        return prices[0], None
    current = prices[0]
    previous = prices[-1]
    # Köhnə qiymət cari qiymətdən 4 dəfədən çox böyükdürsə, o, qiymət deyil (məs. qram)
    if previous > current * 4:
        return current, None
    return current, previous


# ------------------------------------------------------------------ əsas funksiya


def clean_text(raw_text: str) -> CleanResult:
    """Xam mətn -> məhsul namizədi sətirlər + statistika."""
    dropped: dict[str, int] = {}
    kept: list[CleanLine] = []
    total = 0

    for raw_line in raw_text.splitlines():
        raw_line = raw_line.rstrip()
        if not raw_line.strip():
            continue
        total += 1

        text = fix_ocr_digits(normalize(raw_line))
        prices = extract_prices(text)

        reason = is_noise(text, prices)
        if reason:
            dropped[reason] = dropped.get(reason, 0) + 1
            continue

        price, old_price = split_prices(prices)
        kept.append(CleanLine(raw=raw_line.strip(), text=text, prices=prices,
                              price=price, old_price=old_price))

    stats = {
        "total_lines": total,
        "kept": len(kept),
        "dropped": dropped,
        "keep_ratio": round(len(kept) / total, 3) if total else 0.0,
    }
    return CleanResult(lines=kept, stats=stats)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("İstifadə: python -m ingestion.cleaner <mətn faylı>")
        raise SystemExit(1)

    result = clean_text(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(result.stats)
    for line in result.lines[:40]:
        print(f"  {line.price!s:>8}  {line.old_price!s:>8}  {line.text[:70]}")
