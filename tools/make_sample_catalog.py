"""
Sınaq üçün süni kataloq şəkli yaradır.

    python tools/make_sample_catalog.py            -> Bravo kataloqu
    python tools/make_sample_catalog.py araz       -> Araz kataloqu

İKİ VARİANT VAR VƏ BU QƏSDƏNDİR:
Araz kataloqunda eyni məhsullar FƏRQLİ yazılıb ("Milla süd 1000 ml" vs
"Süd Milla 2.5% 1 L"). Matching məhz bunu həll etməlidir - eyni yazılışlarla
sınamaq heç nə sübut etməzdi.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

BRAVO_ROWS = [
    ("Süd Milla 2.5% 1 L", "1,89", "2,45"),
    ("Düyü Basmati 1 kq", "3,40", ""),
    ("Günəbaxan yağı Sola 1.8 L", "6,20", "8,40"),
    ("Su Sirab 1,5 l", "0,60", ""),
    ("Kərə yağı President 200 q", "7,95", "9,50"),
    ("Şəkər Tozu 1 kq", "1,45", ""),
    ("Makaron Barilla 500 q", "2,10", "2,80"),
    ("Yumurta 10 ədəd", "2,35", ""),
]

# Eyni məhsullar, fərqli yazılış və fərqli qiymət
ARAZ_ROWS = [
    ("Milla süd 1000 ml 2.5%", "2,05", ""),
    ("Basmati düyüsü 1000 q", "3,15", "3,90"),
    ("Sola günəbaxan yağ 1,8 L", "5,95", ""),
    ("Sirab su 1.5 L", "0,55", ""),
    ("President kərə yağı 200 qr", "8,20", ""),
    ("Barilla makaronu 500 qr", "1,95", "2,60"),
    ("Toyuq yumurtası 10 əd", "2,20", ""),
    ("Çay Azercay 250 q", "3,80", ""),   # yalnız Araz-da var
]

VARIANTS = {
    "bravo": ("BRAVO SUPERMARKET", "www.bravo.az", BRAVO_ROWS, "sample_catalog.png"),
    "araz": ("ARAZ MARKET", "www.arazmarket.az", ARAZ_ROWS, "sample_catalog_araz.png"),
}

FONTS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def load_font(size: int):
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("TrueType şrift tapılmadı")


def main() -> None:
    variant = (sys.argv[1] if len(sys.argv) > 1 else "bravo").lower()
    if variant not in VARIANTS:
        raise SystemExit(f"Naməlum variant: {variant}. İcazəli: {', '.join(VARIANTS)}")
    title, site, rows, filename = VARIANTS[variant]

    title_font = load_font(46)
    row_font = load_font(32)
    note_font = load_font(24)

    width, height = 1200, 180 + len(rows) * 70 + 120
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    draw.text((60, 45), title, fill="black", font=title_font)
    draw.text((60, 105), "Həftəlik endirimlər — 12 mart tarixinə qədər etibarlıdır",
              fill="#555555", font=note_font)
    draw.line([(60, 155), (width - 60, 155)], fill="#999999", width=2)

    y = 185
    for name, price, old in rows:
        draw.text((60, y), name, fill="black", font=row_font)
        draw.text((820, y), price, fill="black", font=row_font)
        if old:
            draw.text((1000, y), old, fill="#777777", font=row_font)
            # üstündən xətt çəkilmiş köhnə qiymət
            draw.line([(995, y + 22), (1105, y + 22)], fill="#777777", width=2)
        y += 70

    draw.text((60, y + 30), f"{site}  •  Əlaqə: 012 000 00 00",
              fill="#555555", font=note_font)

    settings.ensure_dirs()
    out = settings.data_dir / filename
    img.save(out)
    print(f"Yaradıldı: {out}  ({title}, {len(rows)} məhsul)")


if __name__ == "__main__":
    main()
