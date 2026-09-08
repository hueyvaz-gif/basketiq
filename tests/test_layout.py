"""
Layout analizi testləri - "kart" tapan OCR.

Real kataloq şəkli repo-ya qoyula bilməz (müəllif hüququ), ona görə PIL ilə
süni kart şəbəkəsi çəkirik: ad yuxarıda, qiymət aşağıda qırmızı qutuda,
üstündə sarı qutuda köhnə qiymət. Bu, kart quruluşlu kataloqu təkrarlayır.

Testlərin əsas sualı: qiymət DÜZGÜN məhsula yapışırmı? Səhv yapışma ən
təhlükəli səhvdir, çünki nəticə "düzgün görünür" - sadəcə yanlışdır.
"""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from ingestion.cleaner import clean_text
from ingestion.layout import (
    Card,
    RED_RANGE,
    YELLOW_RANGE,
    _cluster,
    _first_at_or_after,
    color_mask,
    find_boxes,
    parse_page,
    parse_price,
)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# (ad, ölçü, yeni qiymət, köhnə qiymət)
PRODUCTS = [
    ("Eskimo dondurma", "60 q", "0.55", "0.69"),
    ("Basmati duyu", "1 kq", "3.40", "4.20"),
    ("Zeytun yagi", "1 L", "8.90", "9.99"),
    ("Sirab su", "1.5 L", "0.60", "0.75"),
    ("Servelat kolbasa", "kq", "12.99", "15.69"),
    ("Kartof fri", "2.5 kq", "8.99", "13.79"),
]

COLS, ROWS = 3, 2
CARD_W, CARD_H = 420, 460


def _font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return None


@pytest.fixture(scope="module")
def card_page() -> Image.Image:
    """Kart quruluşunda süni kataloq səhifəsi."""
    font = _font(30)
    if font is None:
        pytest.skip("TrueType şrift tapılmadı - layout testi ötürülür")
    price_font = _font(64)
    small_font = _font(26)

    img = Image.new("RGB", (COLS * CARD_W, ROWS * CARD_H), "white")
    draw = ImageDraw.Draw(img)

    for i, (name, size, new_price, old_price) in enumerate(PRODUCTS):
        cx = (i % COLS) * CARD_W
        cy = (i // COLS) * CARD_H

        # mətn bloku - kartın yuxarısında
        draw.text((cx + 30, cy + 30), name, fill="black", font=font)
        draw.text((cx + 30, cy + 70), size, fill="black", font=small_font)

        # köhnə qiymət: sarı qutu, üstündən qırmızı xətt
        yx0, yy0 = cx + 150, cy + 250
        yx1, yy1 = cx + 390, cy + 320
        draw.rectangle([yx0, yy0, yx1, yy1], fill=(255, 237, 0))
        draw.text((yx0 + 45, yy0 + 12), old_price, fill="black", font=price_font)
        draw.line([yx0 + 30, (yy0 + yy1) // 2, yx1 - 30, (yy0 + yy1) // 2],
                  fill=(227, 6, 19), width=6)

        # yeni qiymət: qırmızı qutu, ağ rəqəmlər
        rx0, ry0 = cx + 150, cy + 322
        rx1, ry1 = cx + 390, cy + 430
        draw.rectangle([rx0, ry0, rx1, ry1], fill=(227, 6, 19))
        draw.text((rx0 + 35, ry0 + 18), new_price, fill="white", font=price_font)

    return img


# ------------------------------------------------------------------ vahid testlər


def test_qiymet_formati_qepiyi_iki_reqem_sayir():
    # Kataloqda qəpik yuxarı indeksdir və OCR nöqtəni tez-tez itirir
    assert parse_price("899") == 8.99
    assert parse_price("0.55") == 0.55
    assert parse_price("3,99") == 3.99
    assert parse_price("13.19") == 13.19


def test_agilabatan_olmayan_qiymet_atilir():
    assert parse_price("12") is None          # 3 rəqəmdən az
    assert parse_price("1234567") is None     # həddən artıq uzun
    assert parse_price("") is None
    assert parse_price("abc") is None


def test_qirmizi_qutu_maskada_tapilir():
    img = Image.new("RGB", (400, 300), "white")
    ImageDraw.Draw(img).rectangle([100, 120, 300, 220], fill=(227, 6, 19))
    boxes = find_boxes(color_mask(img, RED_RANGE), 50, 40)
    assert len(boxes) == 1
    x0, y0, x1, y1 = boxes[0]
    # Maska 8 piksel dəqiqliklə işləyir - tam bərabərlik gözləmirik
    assert abs(x0 - 100) <= 8 and abs(y0 - 120) <= 8
    assert abs(x1 - 300) <= 8 and abs(y1 - 220) <= 8


def test_sari_qutu_qirmizi_ile_qarisdirilmir():
    img = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([50, 50, 250, 120], fill=(255, 237, 0))
    d.rectangle([50, 130, 250, 220], fill=(227, 6, 19))
    assert len(find_boxes(color_mask(img, YELLOW_RANGE), 50, 30)) == 1
    assert len(find_boxes(color_mask(img, RED_RANGE), 50, 30)) == 1


def test_soz_ozunden_sonraki_lovbere_baglanir():
    centers = [100.0, 400.0, 700.0]
    # 350 -> 400 (özündən sonrakı ilk mərkəz)
    assert _first_at_or_after(centers, 350, 0) == 1
    # 410 mərkəzdən bir az aşağıdır, dözümlülük onu geri qaytarır
    assert _first_at_or_after(centers, 410, 30) == 1
    # dözümlülük olmasa növbətiyə keçir
    assert _first_at_or_after(centers, 410, 0) == 2
    assert _first_at_or_after(centers, 900, 0) is None


def test_yaxin_koordinatlar_bir_sutuna_yigilir():
    assert _cluster([100, 105, 400, 402, 700], 50) == [102.5, 401.0, 700.0]


def test_kart_setri_sondaki_zibili_qiymete_yapisdirmir():
    # "205," + "13.19" -> "205,13.19" olsaydı, cleaner bunu 205.13 oxuyardı
    card = Card(text="Sədəf servelat kq 205,", price=13.19, old_price=17.59)
    line = card.as_line()
    assert line == "Sədəf servelat kq 205 13.19 17.59"
    cleaned = clean_text(line)
    assert cleaned.lines[0].price == 13.19
    assert cleaned.lines[0].old_price == 17.59


# ------------------------------------------------------------------ uçdan-uca


def test_kartli_sehifede_butun_mehsullar_tapilir(card_page):
    result = parse_page(card_page)
    assert len(result.cards) == len(PRODUCTS), (
        f"{len(PRODUCTS)} kart gözlənilirdi, {len(result.cards)} tapıldı"
    )


def test_qiymet_oz_mehsuluna_yapisir(card_page):
    """Ən vacib test: ad ilə qiymətin cütləşməsi."""
    result = parse_page(card_page)

    for card in result.cards:
        matches = [p for p in PRODUCTS if p[0].split()[0].lower() in card.text.lower()]
        if not matches:
            continue  # OCR adı oxuya bilməyib - bu, ayrı testin mövzusudur
        assert len(matches) == 1, f"Bir kartda iki məhsul adı var: {card.text!r}"
        name, _size, new_price, _old = matches[0]
        assert card.price == float(new_price), (
            f"'{name}' üçün qiymət {card.price}, gözlənilən {new_price}"
        )


def test_kart_setirleri_cleaner_terefinden_qebul_olunur(card_page):
    """Layout çıxışı pipeline-ın qalanına uyğun formatdadır."""
    cleaned = clean_text(parse_page(card_page).text)
    assert cleaned.stats["kept"] >= len(PRODUCTS) - 1
    for line in cleaned.lines:
        assert line.price is not None
        if line.old_price is not None:
            assert line.old_price > line.price, "Köhnə qiymət yenidən böyük olmalıdır"


def test_kartsiz_sehifede_bos_netice(card_page):
    """Qiymət qutusu olmayan səhifə - çağıran tərəf adi OCR-a qayıtmalıdır."""
    plain = Image.new("RGB", (800, 600), "white")
    font = _font(30)
    if font is not None:
        ImageDraw.Draw(plain).text((50, 50), "Sud Milla 1 L 1,89", fill="black", font=font)
    result = parse_page(plain)
    assert result.cards == []
