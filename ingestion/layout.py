"""
Kataloq səhifəsinin QURULUŞ analizi - "kart" tapan OCR.

PROBLEM (real kataloqda ölçülüb, qlyanslı endirim jurnalı):
Adi sətir-əsaslı OCR bu səhifələrdə 43 sətirdən 0 məhsul çıxarır. Səbəb odur ki,
qlyanslı kataloq SƏTİRLƏRDƏN ibarət deyil - o, KARTLAR şəbəkəsidir:

    ┌─────────────────────────┐
    │ Hər Gün          <- brend (boz, kiçik)
    │ Eskimo dondurma  <- ad (qara, qalın)
    │ 8.5% 60 q        <- ölçü
    │      [şəkil]
    │              ┌────────┐
    │              │ 0.69   │ <- SARI qutu, üstündən xətt = köhnə qiymət
    │              ├────────┤
    │              │ 0.55   │ <- QIRMIZI qutu, ağ rəqəm = yeni qiymət
    │              └────────┘
    └─────────────────────────┘

Ad yuxarı solda, qiymət aşağı sağda - AYRI bloklardadır. Tesseract onları
sətir kimi birləşdirə bilmir, çünki aralarında şəkil var.

HƏLL: qiymət qutusunu RƏNGƏ görə tapırıq və onu kartın "lövbəri" sayırıq.
Sonra hər sözü ən yaxın lövbərə bağlayırıq. Nəticədə hər kartdan bir sətir çıxır:

    "Hər Gün Eskimo dondurma 8.5% 60 q 0.55 0.69"

Bu format pipeline-ın qalanına TAM UYĞUNDUR - cleaner qiymətləri sıralayıb ən
kiçiyini cari, ən böyüyünü köhnə qiymət sayır. Yəni bu modul mövcud zəncirə
heç nə dəyişmədən qoşulur.

ÖLÇÜLMÜŞ NƏTİCƏ (qlyanslı endirim jurnalı, səhifə 2, 10 məhsul):
    ad:            10/10
    yeni qiymət:   10/10
    köhnə qiymət:  10/10
    vaxt:          ~15-30 san/səhifə
    Müqayisə üçün: adi sətir-əsaslı OCR eyni səhifədə 0/10.

Araz Market (fərqli dizayn, 8 məhsul): 5 kart, qiymətlərin 4-ü düzgün.
Niyə daha aşağı? Araz-da qiymət 2 ölçülü yazılır (böyük "1", sağ yuxarısında
kiçik "99", altında "₼") - Tesseract-ın sətir modeli bunu çətin tutur. Üstəlik
səhifənin sağ sütununda qiymət ümumiyyətlə qutusuzdur, sadəcə qırmızı mətndir,
yəni lövbər yoxdur. Bu, bilinən məhdudiyyətdir.

QEYD (BasketIQ v2): aşağıdakı ölçmələr kart quruluşlu kataloqlar üzərində aparılıb və
metodun özü dəyişmir. Həmin mənbə artıq işlədilmir - indi yeganə kataloq mənbəyi
Araz-dır, yəni real işdə bu metod məhz yuxarıdakı DAHA ZƏİF halda işləyir
(5 kartdan 4 qiymət). Bunu "10/10" kimi oxumaq səhv olar.

NİYƏ numpy/OpenCV yoxdur? Layihənin asılılıqlarını böyütməmək üçün. Maskalar
PIL-in band əməliyyatları ilə qurulur (C sürəti), komponent axtarışı isə 8 dəfə
kiçildilmiş maskada işləyir - 4.8 milyon piksel əvəzinə 75 min.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

import pytesseract
from PIL import Image, ImageChops, ImageOps

from app.config import settings
from ingestion.tess import configure_tesseract

# Maskanı bu qədər kiçildirik: qiymət qutusu ~200 piksel enindədir,
# 8 dəfə kiçildikdən sonra da 25 piksel qalır - tapmaq üçün bol-bol yetər.
DOWNSCALE = 8

# Rəng aralıqları (r_min, r_max, g_min, g_max, b_min, b_max)
RED_RANGE = (150, 255, 0, 90, 0, 90)        # yeni qiymət qutusu
YELLOW_RANGE = (200, 255, 190, 255, 0, 120)  # köhnə qiymət qutusu

# Qiymət qutusunun forması: eni hündürlüyündən 1.2-4 dəfə böyükdür.
# Bu şərt loqoları (kvadrata yaxın) və alt bannerləri (çox uzun) kənarlaşdırır.
MIN_ASPECT, MAX_ASPECT = 1.2, 4.0

MIN_PRICE, MAX_PRICE = 0.05, 999.0

# Rəng maskası qutunu rəqəmlərin kənarından KƏSİR (fon sarıdır, rəqəm qara).
# Kəsilmiş rəqəmi Tesseract səhv oxuyur. Ölçülüb: kənarsız 6/10 düz + 3 SƏHV,
# 10% kənarla 10/10 düz + 0 səhv.
BOX_PAD_RATIO = 0.10

# Köhnə qiymət yenidən böyük olmalıdır, amma 4 dəfədən çox yox -
# əks halda bu, qiymət deyil, OCR səhvidir.
MAX_DISCOUNT_RATIO = 4.0

WORD_MIN_CONF = 40

# Söz lövbər mərkəzindən bu qədər (xana addımının payı) aşağı/sağa düşə bilər
# və hələ də "ondan əvvəl" sayılır. Ölçülüb: 0.05-0.20 aralığında nəticə
# eynidir, 0.30-da isə kart qonşu sıranın adını da udur.
WORD_TOLERANCE = 0.15

# Kataloqun sabit etiketləri - məhsul haqqında heç nə demir.
# Niyə burada atırıq? "endirim" sözü cleaner-in reklam süzgəcini işə salır və
# tam düzgün kart sətri "reklam mətni" kimi atılırdı. Üstəlik bu sözlər LLM-in
# prompt-unu uzadır, faydası isə sıfırdır.
BADGE_WORDS = {
    "endirim", "endirimlə", "endirimli", "endirimlər", "qənaətli", "qenaetli",
    "daha", "yalnız", "yalniz", "hədiyyə", "hediyye",
}


@dataclass
class Card:
    """Bir məhsul kartı: mətn bloku + qiymətlər."""

    text: str
    price: float | None = None
    old_price: float | None = None
    box: tuple[int, int, int, int] = (0, 0, 0, 0)

    def as_line(self) -> str:
        """
        Kartı bir sətrə çevirir: "ad ... yeni köhnə".

        Qiymətlər sonda və məhz bu sırada yazılır ki, cleaner-in mövcud
        məntiqi (ən kiçik = cari qiymət) düzgün işləsin.
        """
        # Sondakı durğu işarələri qiymətə yapışıb onu korlayır:
        # "... 205," + "13.19" -> "205,13.19" (cleaner bunu 205.13 kimi oxuyur)
        text = re.sub(r"[^\w%)]+$", "", self.text).strip()
        parts = [text]
        if self.price is not None:
            parts.append(f"{self.price:.2f}")
        if self.old_price is not None:
            parts.append(f"{self.old_price:.2f}")
        return " ".join(p for p in parts if p).strip()


@dataclass
class LayoutResult:
    cards: list[Card] = field(default_factory=list)
    anchors: int = 0          # tapılan qırmızı qutu sayı (filtrdən əvvəl)

    @property
    def text(self) -> str:
        return "\n".join(card.as_line() for card in self.cards)


# ---------------------------------------------------------------- rəng maskaları


def color_mask(img: Image.Image, rng: tuple) -> Image.Image:
    """Verilmiş RGB aralığına düşən piksellər ağ, qalanı qara."""
    r, g, b = img.convert("RGB").split()
    lo_r, hi_r, lo_g, hi_g, lo_b, hi_b = rng
    mr = r.point(lambda v: 255 if lo_r <= v <= hi_r else 0)
    mg = g.point(lambda v: 255 if lo_g <= v <= hi_g else 0)
    mb = b.point(lambda v: 255 if lo_b <= v <= hi_b else 0)
    return ImageChops.multiply(ImageChops.multiply(mr, mg), mb)


def find_boxes(mask: Image.Image, min_w: int, min_h: int) -> list[tuple]:
    """
    Maskadakı bağlı sahələrin çərçivələri (flood fill).

    Kiçildilmiş maskada işləyir - saf Python-da 4.8 milyon piksel gəzmək
    saniyələr çəkərdi, 75 min piksel isə göz qırpımıdır.
    """
    small = mask.resize(
        (max(1, mask.width // DOWNSCALE), max(1, mask.height // DOWNSCALE)), Image.BOX
    )
    px = small.load()
    width, height = small.size
    seen = [[False] * width for _ in range(height)]
    boxes = []

    for y in range(height):
        for x in range(width):
            if px[x, y] < 128 or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            x0 = x1 = x
            y0 = y1 = y
            while stack:
                cx, cy = stack.pop()
                if cx < x0:
                    x0 = cx
                if cx > x1:
                    x1 = cx
                if cy < y0:
                    y0 = cy
                if cy > y1:
                    y1 = cy
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        if not seen[ny][nx] and px[nx, ny] >= 128:
                            seen[ny][nx] = True
                            stack.append((nx, ny))

            box = (x0 * DOWNSCALE, y0 * DOWNSCALE, (x1 + 1) * DOWNSCALE, (y1 + 1) * DOWNSCALE)
            if box[2] - box[0] >= min_w and box[3] - box[1] >= min_h:
                boxes.append(box)

    return boxes


# ---------------------------------------------------------------- qiymət oxuma


def parse_price(text: str) -> float | None:
    """
    '899' -> 8.99,  '0.55' -> 0.55,  '3,99' -> 3.99.

    Niyə belə? Kataloqda qəpik hissəsi yuxarı indeks kimi kiçik yazılır və
    OCR nöqtəni tez-tez itirir. Amma Azərbaycan qiymətində qəpik HƏMİŞƏ
    2 rəqəmdir - ona görə sonuncu iki rəqəmi qəpik sayırıq. Bu, uydurma deyil,
    formatın qaydasıdır.
    """
    digits = re.sub(r"[^0-9]", "", text or "")
    if len(digits) < 3 or len(digits) > 6:
        return None
    value = int(digits[:-2]) + int(digits[-2:]) / 100
    return value if MIN_PRICE <= value <= MAX_PRICE else None


def _ocr_digits(img: Image.Image, psm: int, upscale: int = 2) -> str:
    big = img.resize((img.width * upscale, img.height * upscale), Image.LANCZOS)
    return pytesseract.image_to_string(
        big,
        lang=settings.tesseract_langs,
        config=f"--psm {psm} -c tessedit_char_whitelist=0123456789.,",
    ).strip()


def _ocr_digits_free(img: Image.Image, upscale: int = 3) -> str:
    """
    Whitelist OLMADAN oxuyur və rəqəmləri özümüz süzürük.

    Niyə? Tesseract 5-in LSTM mühərrikində `tessedit_char_whitelist` bəzən
    çıxışı tamamilə boğur - ölçülüb: whitelist ilə '', whitelist-siz '| 199'.
    Rəqəmi filtrləmək bizim üçün bir regex-dir, itirilmiş cavabı isə geri
    qaytarmaq mümkün deyil.
    """
    big = img.resize((img.width * upscale, img.height * upscale), Image.LANCZOS)
    # Tesseract mətn kadrın kənarına toxunanda çaşır - ağ haşiyə əlavə edirik
    big = ImageOps.expand(big, border=big.height // 4, fill=255)
    text = pytesseract.image_to_string(
        big, lang=settings.tesseract_langs, config="--psm 7"
    )
    return re.sub(r"[^0-9]", "", text)


def pad_box(page: Image.Image, box: tuple, ratio: float = BOX_PAD_RATIO) -> tuple:
    """Qutunu hər tərəfdən genişləndirir - kəsilmiş rəqəm OCR-ın baş düşmənidir."""
    pad = int((box[3] - box[1]) * ratio)
    return (
        max(0, box[0] - pad),
        max(0, box[1] - pad),
        min(page.width, box[2] + pad),
        min(page.height, box[3] + pad),
    )


def _read_price_split(crop: Image.Image) -> float | None:
    """
    Qiyməti İKİ HİSSƏ kimi oxuyur: sol = manat, sağ yuxarı = qəpik.

    Niyə ikinci üsul lazımdır? Araz-ın kataloqunda qiymət 2 ÖLÇÜLÜ düzülür:
    böyük "0", onun sağ yuxarısında kiçik "59", altında isə "₼". Tesseract-ın
    sətir modeli bunu tuta bilmir - tam qutunu oxumağa çalışanda boş qaytarır.
    Hissələri ayrı-ayrı versək, hər biri adi bir sətir olur.

    Ölçülüb (Araz, 8 qiymət): tam qutu 1/8, bölmə 5/8.
    kart kataloqunda isə əksinə (tam 10/10, bölmə 7/10) - ona görə bu, YALNIZ ehtiyat
    yoldur, birinci üsul nəticə verməyəndə işə düşür.
    """
    width, height = crop.size
    manat = _ocr_digits_free(crop.crop((0, 0, int(width * 0.60), height)))
    qepik = _ocr_digits_free(crop.crop((int(width * 0.55), 0, width, int(height * 0.65))))
    if not manat or len(qepik) != 2:
        return None
    try:
        value = float(f"{int(manat)}.{qepik}")
    except ValueError:
        return None
    return value if MIN_PRICE <= value <= MAX_PRICE else None


def read_new_price(page: Image.Image, box: tuple) -> float | None:
    """
    Qırmızı qutu: ağ rəqəmlər -> ağ fonda qara rəqəmlər.

    Burada qutuya kənar ƏLAVƏ EDİLMİR (sarı qutudan fərqli olaraq). Səbəb:
    bu çevirmədə "parlaq piksel = mətn" sayılır, kənardakı ağ səhifə fonu da
    rəqəmə çevrilər. Ölçülüb: kənarsız 10/10, 10% kənarla 4/10.
    """
    crop = page.crop(box).convert("L").point(lambda v: 0 if v > 150 else 255, mode="L")
    value = parse_price(_ocr_digits(crop, psm=8))
    if value is None:
        value = _read_price_split(crop)
    return value


def read_old_price(page: Image.Image, box: tuple, new_price: float | None) -> float | None:
    """
    Sarı qutu: qara rəqəmlər, amma üstündən qırmızı xətt keçir.

    Xətt rəqəmləri birləşdirib OCR-ı çaşdırır (13.79 -> 1337.29). Ona görə
    üç fərqli psm ilə oxuyub nəticələri SÜZÜRÜK: köhnə qiymət yenidən böyük,
    amma 4 dəfədən çox böyük olmamalıdır. Sağ qalan variantlardan ən çox
    təkrarlananı seçirik.

    Niyə belə ehtiyatlı? Səhv köhnə qiymət "saxta endirim" bayrağını yalandan
    qaldırar. Bilməmək, səhv bilməkdən yaxşıdır - şübhəlisini None qaytarırıq.
    """
    crop = page.crop(pad_box(page, box))
    crop = crop.convert("L").point(lambda v: 0 if v < 128 else 255, mode="L")

    candidates = []
    for psm in (7, 8, 13):
        value = parse_price(_ocr_digits(crop, psm=psm))
        if value is None:
            continue
        if new_price is not None:
            if value <= new_price or value > new_price * MAX_DISCOUNT_RATIO:
                continue
        candidates.append(value)

    if not candidates:
        return None
    return Counter(candidates).most_common(1)[0][0]


# ---------------------------------------------------------------- söz qutuları


def page_words(page: Image.Image) -> list[dict]:
    """Səhifədəki sözlər + koordinatları (psm 11 = səpələnmiş mətn)."""
    data = pytesseract.image_to_data(
        page,
        lang=settings.tesseract_langs,
        config="--psm 11",
        output_type=pytesseract.Output.DICT,
    )
    words = []
    for i, raw in enumerate(data["text"]):
        text = (raw or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < WORD_MIN_CONF:
            continue
        words.append({
            "text": text,
            "x": data["left"][i],
            "y": data["top"][i],
            "w": data["width"][i],
            "h": data["height"][i],
        })
    return words


def on_white_background(page: Image.Image, word: dict, pad: int = 6) -> bool:
    """
    Sözün fonu ağdırmı?

    Kataloq mətni ağ fonda yazılır; məhsul şəklinin ÜSTÜNDƏKİ yazı isə
    qablaşdırmanın öz brendidir ("ESKIMO", "МИРАТОРГ") - o, məhsulun adı deyil.
    Fonun rənginə baxmaq bu ikisini ayırmağın ən ucuz yoludur.
    """
    x0 = max(0, word["x"] - pad)
    y0 = max(0, word["y"] - pad)
    x1 = min(page.width, word["x"] + word["w"] + pad)
    y1 = min(page.height, word["y"] + word["h"] + pad)
    if x1 <= x0 or y1 <= y0:
        return False

    crop = page.crop((x0, y0, x1, y1)).convert("RGB").resize((8, 8))
    lum = sorted(
        0.299 * crop.getpixel((x, y))[0]
        + 0.587 * crop.getpixel((x, y))[1]
        + 0.114 * crop.getpixel((x, y))[2]
        for y in range(8)
        for x in range(8)
    )
    brightest = lum[len(lum) * 3 // 4:]     # ən parlaq 25% = fon
    return sum(brightest) / len(brightest) > 215


def group_into_lines(words: list[dict]) -> str:
    """
    Sözləri vizual sətirlərə yığır və hər sətirdə soldan sağa düzür.

    Niyə lazımdır? Sadəcə y-ə görə sıralasaq, eyni sətirdəki sözlər bir neçə
    piksel fərqinə görə qarışır: "Hər Gün" -> "Gün Hər".
    """
    if not words:
        return ""

    heights = sorted(w["h"] for w in words)
    tolerance = max(6, heights[len(heights) // 2] * 0.6)

    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: w["y"] + w["h"] / 2):
        center = word["y"] + word["h"] / 2
        if lines and abs(center - lines[-1][0]["_center"]) <= tolerance:
            lines[-1].append(word)
        else:
            word = {**word, "_center": center}
            lines.append([word])

    out = []
    for line in lines:
        line.sort(key=lambda w: w["x"])
        tokens = [w["text"] for w in line if any(ch.isalnum() for ch in w["text"])]
        if tokens:
            out.append(" ".join(tokens))
    return " ".join(out).strip()


# ---------------------------------------------------------------- əsas funksiya


def _inside_any(word: dict, boxes: list[tuple]) -> bool:
    cx = word["x"] + word["w"] // 2
    cy = word["y"] + word["h"] // 2
    return any(b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for b in boxes)


def _cluster(values: list[float], tolerance: float) -> list[float]:
    """Yaxın koordinatları bir sütuna/sıraya yığır və mərkəzlərini qaytarır."""
    groups: list[list[float]] = []
    for value in sorted(values):
        if groups and value - groups[-1][-1] <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(g) / len(g) for g in groups]


BIN = 4  # boşluq axtarışında piksel addımı


def _occupied_bins(words: list[dict], axis: str, limit: int) -> list[bool]:
    """Sözlərin oxa proyeksiyası: hansı zolaqlarda mətn var?"""
    bins = [False] * (limit // BIN + 2)
    for word in words:
        start = word["x"] if axis == "x" else word["y"]
        size = word["w"] if axis == "x" else word["h"]
        for b in range(start // BIN, (start + size) // BIN + 1):
            if 0 <= b < len(bins):
                bins[b] = True
    return bins


def _valley(bins: list[bool], low: float, high: float) -> float:
    """
    İki lövbər arasındakı ƏN GENİŞ boş zolağın ortası.

    Niyə sadəcə iki lövbərin ortası deyil? Çünki lövbərin kartdakı yeri
    kataloqdan kataloqa dəyişir: kart kataloqunda qiymət kartın ALTINDA, Araz-da isə
    ORTASINDA durur. kart kataloqunda «iki lövbərin ortası» sərhədi kartın öz adından
    aşağı düşür və ad qonşu kartın olur (ölçüldü: 10 kartdan 6-sı qarışdı).
    Mətnin özündəki boşluq isə həqiqi sərhəddir - kartlar arasında ağ zolaq var.
    """
    start = int(low) // BIN
    end = min(len(bins) - 1, int(high) // BIN)
    best_len, best_mid = 0, None
    run_start = None
    for b in range(start, end + 1):
        if not bins[b]:
            if run_start is None:
                run_start = b
        else:
            if run_start is not None and b - run_start > best_len:
                best_len, best_mid = b - run_start, (run_start + b) / 2
            run_start = None
    if run_start is not None and end + 1 - run_start > best_len:
        best_len, best_mid = end + 1 - run_start, (run_start + end + 1) / 2
    if best_mid is None:
        return (low + high) / 2
    return best_mid * BIN


def _bounds(
    centers: list[float], low: float, high: float, bins: list[bool] | None = None
) -> list[tuple[float, float]]:
    """
    Mərkəzlərdən xana sərhədləri.

    Kənar xanalar səhifənin kənarına qədər uzanır - kartın adı çox vaxt
    lövbərdən xeyli solda/yuxarıda başlayır və kəsilməməlidir.
    """
    if bins is None:
        edges = [(centers[i] + centers[i + 1]) / 2 for i in range(len(centers) - 1)]
    else:
        edges = [_valley(bins, centers[i], centers[i + 1]) for i in range(len(centers) - 1)]

    out = []
    for i, _ in enumerate(centers):
        left = edges[i - 1] if i > 0 else low
        right = edges[i] if i < len(centers) - 1 else high
        out.append((left, right))
    return out


def _nearest(centers: list[float], value: float) -> int:
    return min(range(len(centers)), key=lambda i: abs(centers[i] - value))


def _first_at_or_after(centers: list[float], value: float, tolerance: float) -> int | None:
    """
    Verilmiş nöqtədən sonra gələn ilk mərkəzin indeksi.

    tolerance qədər geridə qalan mərkəz də "sonra" sayılır - söz lövbərin
    mərkəzindən bir az aşağı/sağa düşə bilər.

    SÖZÜN LÖVBƏRDƏN MƏSAFƏSİ BURADA MƏHDUDLAŞDIRILMIR. Sınandı və ölçüldü:
    `_grid_step()` kartın eni DEYİL - o, qonşu qiymət qutuları arasındakı
    median məsafədir və qutular yan-yana düşəndə kiçilir (6-cı səhifədə 112,
    halbuki kart ~250 pikseldir). Həmin dəyəri sərhəd kimi işlətmək kartın
    ÖZ sözlərini kəsirdi: «Nestle Damak Şokolad» -> «Şokolad», «Lotte Choco
    Pie» -> «Lotte Pie». Sərhəd əvəzinə şəbəkənin özü düzəldildi (bax
    `parse_page`: xanalar bütün qırmızı qutulardan qurulur).
    """
    for i, center in enumerate(centers):
        if center >= value - tolerance:
            return i
    return None


# Qiyməti oxunmayan qutu şəbəkəyə yalnız ÖLÇÜSÜ qiymət qutusuna oxşayanda
# buraxılır. Ölçüldü: bu süzgəc olmadan endirim nişanı («32%» qırmızı ləkəsi)
# da xana tuturdu və qonşu kartın sözlərini udurdu - «Snickers/Bounty/Mars/Twix
# Mini şokolad» kartı tamamilə boşaldı.
LANDMARK_MIN, LANDMARK_MAX = 0.6, 1.6


def _grid_landmarks(red_boxes: list[tuple], priced: list[tuple]) -> list[tuple]:
    """
    Şəbəkəni quran qutular: qiyməti oxunanların HAMISI + ölçüsü onlara
    oxşayan qiymətsizlər.

    Qiymətsiz qutu kart yaratmır, amma öz xanasını tutur - belədə onun sözləri
    qonşu kartın mətninə axmır, sadəcə atılır.
    """
    if not priced:
        return red_boxes
    ws = sorted(b[2] - b[0] for b in priced)
    hs = sorted(b[3] - b[1] for b in priced)
    mw, mh = ws[len(ws) // 2], hs[len(hs) // 2]

    known = set(priced)
    out = list(priced)
    for box in red_boxes:
        if box in known:
            continue
        w, h = box[2] - box[0], box[3] - box[1]
        if LANDMARK_MIN * mw <= w <= LANDMARK_MAX * mw and LANDMARK_MIN * mh <= h <= LANDMARK_MAX * mh:
            out.append(box)
    return out


def _grid_step(centers: list[int], fallback: int) -> int:
    """Lövbərlərin arasındakı tipik məsafə = kartın ölçüsü."""
    uniq = sorted(set(centers))
    gaps = [b - a for a, b in zip(uniq, uniq[1:]) if b - a > 100]
    if not gaps:
        return fallback
    return sorted(gaps)[len(gaps) // 2]


def parse_page(page: Image.Image) -> LayoutResult:
    """
    Bir səhifədən məhsul kartlarını çıxarır.

    Kart tapılmasa boş nəticə qaytarır - çağıran tərəf adi OCR-a qayıdır.
    """
    configure_tesseract()

    page = page.convert("RGB")
    min_w = max(30, page.width // 20)   # qiymət qutusu səhifə eninin ~10%-idir
    min_h = max(20, page.height // 40)

    red_boxes = find_boxes(color_mask(page, RED_RANGE), min_w, min_h)
    red_boxes = [
        b for b in red_boxes
        if MIN_ASPECT <= (b[2] - b[0]) / max(1, b[3] - b[1]) <= MAX_ASPECT
    ]
    result = LayoutResult(anchors=len(red_boxes))
    if not red_boxes:
        return result

    yellow_boxes = find_boxes(color_mask(page, YELLOW_RANGE), min_w, min_h // 2)

    # Qiyməti oxunmayan qutu qiymət qutusu deyil (loqo, banner) - atılır
    anchors = []
    for box in red_boxes:
        price = read_new_price(page, box)
        if price is not None:
            anchors.append((box, price))
    if not anchors:
        return result

    words = page_words(page)
    # ŞƏBƏKƏ BÜTÜN QIRMIZI QUTULARDAN QURULUR, yalnız qiyməti oxunanlardan yox.
    #
    # REAL SƏHVDƏN ÇIXIB (ölçüldü: 175 qutudan yalnız 102-sinin qiyməti
    # oxundu). Qiyməti oxunmayan kart şəbəkədən tamamilə çıxırdı və onun
    # sözləri «özündən sonrakı ilk lövbərə» axıb qonşu kartın mətninə
    # qarışırdı - «Penstore Karandaş 12 rəng Penstore Qayçı ASH Su qabi»
    # məhz belə yarandı. İndi belə qutu da öz xanasını SAHİBLƏNİR, sadəcə
    # kart yaratmır: sözləri qonşuya getmir, ATILIR.
    grid_boxes = _grid_landmarks(red_boxes, [b for b, _ in anchors])
    col = _grid_step([(b[0] + b[2]) // 2 for b in grid_boxes], page.width // 3)
    row = _grid_step([(b[1] + b[3]) // 2 for b in grid_boxes], page.height // 3)

    # Sözü hansı karta yazaq? Lövbərlərdən ŞƏBƏKƏ XANALARI qururuq.
    #
    # Niyə "ən yaxın lövbər" deyil? Çünki lövbərin kartdakı yeri kataloqdan
    # kataloqa dəyişir: kart kataloqunda qiymət kartın AŞAĞI SAĞINDA, Araz-da isə
    # ORTA SAĞINDA durur. Kart kataloqunda məhsulun adı öz qiymətindən çox, yuxarıdakı
    # kartın qiymətinə yaxın olur - "ən yaxın" qaydası adları qonşu məhsula
    # yapışdırırdı (ölçüldü: 10 kartdan 3-ü qarışdı).
    #
    # Xana sərhədi isə həndəsi olaraq düzgündür: iki qonşu lövbərin ortası.
    # Bu, hər iki düzülüşdə işləyir, çünki kartlar hər halda şəbəkədədir.
    col_centers = _cluster([(b[0] + b[2]) / 2 for b in grid_boxes], col * 0.5)
    row_centers = _cluster([(b[1] + b[3]) / 2 for b in grid_boxes], row * 0.5)

    # Hər qutu öz şəbəkə xanasını "sahiblənir". Qiyməti oxunmayan qutu xananı
    # tutur, amma dəyəri None-dur - ora düşən söz heç bir karta yazılmır.
    priced_index = {box: i for i, (box, _) in enumerate(anchors)}
    owner: dict[tuple[int, int], int | None] = {}
    for box in grid_boxes:
        ci = _nearest(col_centers, (box[0] + box[2]) / 2)
        ri = _nearest(row_centers, (box[1] + box[3]) / 2)
        index = priced_index.get(box)
        # Xana artıq qiymətli lövbərindirsə, qiymətsiz qutu onu ƏLİNDƏN ALMIR.
        if owner.get((ci, ri)) is None:
            owner[(ci, ri)] = index

    buckets: dict[int, list[dict]] = {i: [] for i in range(len(anchors))}

    for word in words:
        # Qiymət qutularının içindəki rəqəmlər mətnə düşməməlidir - onları
        # ayrıca, daha dəqiq üsulla oxuyuruq (iki dəfə saymaq qiyməti korlayar).
        if _inside_any(word, yellow_boxes) or _inside_any(word, red_boxes):
            continue
        if word["text"].lower().strip(".,:%") in BADGE_WORDS:
            continue
        if not on_white_background(page, word):
            continue

        # Söz özündən SONRA gələn ilk lövbərə aiddir.
        #
        # Bu, kartın oxunuş sırasıdır: əvvəl ad, sonra qiymət. Ölçülmüş
        # koordinatlar bunu təsdiqləyir - kart kataloqunda kartın mətni öz qiymətindən
        # 450 piksel yuxarıdadır, sıra addımı isə 600-dür. Yəni mətn demək olar
        # əvvəlki sıranın qiyməti ilə eyni səviyyədədir; "ən yaxın lövbər" və
        # "iki lövbərin ortası" qaydalarının hər ikisi məhz buna görə səhv edir.
        #
        # `tolerance` sözün lövbər mərkəzindən bir az AŞAĞI düşməsinə icazə
        # verir - Araz-da ad qiymətlə eyni səviyyədədir, tam yuxarıda deyil.
        ci = _first_at_or_after(col_centers, word["x"] + word["w"] / 2, col * WORD_TOLERANCE)
        ri = _first_at_or_after(row_centers, word["y"] + word["h"] / 2, row * WORD_TOLERANCE)
        if ci is None or ri is None:
            continue
        index = owner.get((ci, ri))
        if index is not None:
            buckets[index].append(word)

    order = sorted(range(len(anchors)), key=lambda i: (anchors[i][0][1], anchors[i][0][0]))
    for i in order:
        box, price = anchors[i]
        height = box[3] - box[1]

        # Köhnə qiymət: qırmızının düz üstündəki sarı qutu.
        # Sarı qutu olmayan kataloqda (Araz) köhnə qiymət kart mətnindədir və
        # cleaner onu özü tutur - ona görə burada None qalması problem deyil.
        old_price = None
        for yb in yellow_boxes:
            overlap = min(box[2], yb[2]) - max(box[0], yb[0])
            gap = box[1] - yb[3]
            if overlap > 0.4 * (box[2] - box[0]) and -height * 0.2 <= gap <= height * 0.5:
                old_price = read_old_price(page, yb, price)
                break

        result.cards.append(
            Card(
                text=group_into_lines(buckets[i]),
                price=price,
                old_price=old_price,
                box=box,
            )
        )

    return result
