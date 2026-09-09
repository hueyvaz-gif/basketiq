"""
Məhsul şəkilləri: kataloq səhifəsindən kəsmə + saytdan endirmə.

NİYƏ KƏSİRİK, ENDİRMİRİK?
Trolley məhsul şəkillərini marketin öz onlayn mağazasından götürür. Bizdə belə
mənbə YOXDUR - ölçülüb (`logs/sources.md`): Araz-ın data ünvanlarını
`robots.txt` qadağan edir, Bravo-nun kataloq səhifəsi «0 məhsul» qaytarır,
Bazar Store-un saytı baxımdadır. Yeganə real mənbəyimiz HƏFTƏLİK KATALOQ
ŞƏKLİDİR.

Amma kataloq şəklində məhsulun şəkli VAR - sadəcə səhifənin içindədir.
`ingestion/layout.py` onsuz da hər məhsulun qiymət qutusunu tapır; oradan
kartın XANASINI hesablayıb həmin sahəni kəsmək kifayətdir.

MƏHSULU ŞƏKLƏ NECƏ BAĞLAYIRIQ?
`prices.raw_line` sütununda kartın OCR-dan çıxan ORİJİNAL sətri saxlanılır
(şəffaflıq üçün yazılırdı - indi işə yaradı). Səhifəni yenidən analiz edib
kartların sətirlərini həmin `raw_line` ilə tutuşdururuq. Uyğunluq tam olmaya
bilər (cleaner mətni bir az dəyişir), ona görə `difflib` ilə ƏN YAXIN kart
seçilir və zəif uyğunluq atılır - səhv şəkil göstərməkdənsə placeholder
göstərmək yaxşıdır.

XANA NECƏ HESABLANIR?
`Card.box` kartın özü deyil, QİYMƏT QUTUSUDUR. Məhsulun şəkli qiymətin
ÜSTÜNDƏDİR. Kataloq kartlar şəbəkəsi olduğu üçün sütun və sıra addımını
kartların öz koordinatlarından çıxarmaq olur: iki qonşu qiymət qutusu
arasındakı məsafə = xananın ölçüsü. Xana = qiymət qutusunun mərkəzindən
yuxarı bir sıra addımı, yanlara isə yarım sütun addımı.
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median

from PIL import Image

from app.config import settings

# Şəkillər statik qovluqdadır - server onları birbaşa verir, ayrıca endpoint
# lazım deyil.
PRODUCT_IMAGE_DIR = settings.base_dir / "app" / "static" / "images" / "products"

# Brauzerdəki ünvanın kökü. Bazada yalnız FAYL ADI saxlanılır, tam ünvan isə
# burada qurulur - qovluq dəyişsə, bazadakı 200 sətri yeniləmək lazım gəlmir.
IMAGE_URL_PREFIX = "/static/images/products"

# Şəkli olmayan məhsul üçün neytral fayl. Uydurma məhsul şəkli çəkmirik -
# istifadəçi «bu, həmin məhsuldur» deyə düşünərdi.
PLACEHOLDER_URL = "/static/images/product-placeholder.svg"

# Uyğunluq bundan aşağıdırsa kart məhsula AİD SAYILMIR.
# Səhv şəkil placeholder-dən pisdir: istifadəçi başqa məhsulu görüb qiyməti
# ona aid sayar.
MATCH_THRESHOLD = 0.55

# Kəsilmiş şəklin maksimum ölçüsü. Kataloq səhifəsi 2000+ piksel enindədir,
# kartın xanası isə ~600px - bunu 400-ə endirmək fayl ölçüsünü xeyli azaldır,
# ekranda isə fərq görünmür (kart 220px enindədir).
MAX_SIDE = 400


# İki namizədin fərqi bundan kiçikdirsə, hansının doğru olduğunu bilmirik.
AMBIGUITY_GAP = 0.05


@dataclass
class Assignment:
    """Bir məhsul -> bir kart. `card_index` səhifədəki kartın nömrəsidir."""

    product_id: int
    card_index: int
    score: float


# Səbəblər «uyğunlaşmaya nə qədər yaxın idi» sırası ilə. Bir məhsul bir neçə
# səhifədə yoxlanır; hesabatda ƏN İRƏLİ gedən səbəb yazılır, çünki «qiymət
# yoxdur» (2-ci səhifədə) ilə «kart tutulub» (5-ci səhifədə) eyni məhsul üçün
# eyni vaxtda doğrudur, amma yalnız ikincisi növbəti addımı göstərir.
REASON_ORDER = ("qiymət yoxdur", "zəif", "qeyri-müəyyən", "kart tutulub")


def better_reason(current: str | None, candidate: str) -> str:
    if current is None:
        return candidate
    return max(current, candidate, key=REASON_ORDER.index)


def assign_cards(targets: list[dict], cards: list) -> tuple[list[Assignment], dict[int, str]]:
    """
    Məhsulları səhifədəki kartlara BİR-BİRƏ uyğunlaşdırır.

    ƏVVƏLKİ VARİANT BİR-ÇOXA İDİ VƏ ÖLÇÜLDÜ (`logs/image-check.md`):
    hər məhsul üçün ən yaxşı kart ayrıca seçilirdi, seçilmiş kart isə
    siyahıda qalırdı. Nəticə: 73 şəkildən yalnız 63-ü unikal idi — 20 məhsul
    10 kartı bölüşürdü, yəni hər cütdə ən azı biri səhv şəkil göstərirdi
    («it yemi» üçün plastilin, «paltar yuyucu vasitə» üçün Tuc krekeri).
    Bir kart bir məhsuldur; burada kart tutulandan sonra siyahıdan çıxır.

    QİYMƏT MƏCBURİDİR. Əvvəl `pool = priced or cards` yazılırdı — qiyməti
    uyğun kart tapılmayanda süzgəc TAMAMİLƏ düşürdü və qərarı yalnız mətn
    oxşarlığı verirdi. Qorunma məhz ehtiyac olan anda sönürdü: «sosis» sətri
    Pringles kartına, «qaymaq» plastilinə belə düşdü. İndi qiymət uyğunluğu
    olmayan məhsul şəkilsiz qalır — placeholder səhv şəkildən yaxşıdır.

    SIRA XAL ÜZRƏDİR, bazadakı sıra üzrə yox. Əvvəl kartı «birinci gələn»
    alırdı, yəni nəticə `product_id` sırasından asılı idi. İndi əvvəlcə bütün
    iddialar hesablanır, sonra ən yüksək xaldan aşağı paylanır.
    """
    why: dict[int, str] = {}
    claims: list[Assignment] = []

    for target in targets:
        priced = [
            (index, card)
            for index, card in enumerate(cards)
            if card.price is not None and abs(card.price - target["price"]) < 0.005
        ]
        if not priced:
            why[target["product_id"]] = "qiymət yoxdur"
            continue

        scored = sorted(
            ((similarity(target["raw_line"], card.as_line()), index) for index, card in priced),
            key=lambda pair: pair[0],
            reverse=True,
        )
        score, index = scored[0]

        # HƏDD 0.30 İDİ VƏ SƏHV ŞƏKİL VERİRDİ. Ölçüldü: «Düşbərə Tac 300 q
        # 3,99» sətri «ASH Su qabı 3,99» kartı ilə eyni qiymətə düşür və qısa
        # sətirlərdə oxşarlıq 0.3-ü keçir.
        if score < MATCH_THRESHOLD:
            why[target["product_id"]] = "zəif"
            continue
        if len(scored) > 1 and score - scored[1][0] < AMBIGUITY_GAP:
            why[target["product_id"]] = "qeyri-müəyyən"
            continue

        claims.append(Assignment(target["product_id"], index, score))

    taken: set[int] = set()
    # Bir məhsulun eyni kataloqda BİR NEÇƏ qiymət sətri ola bilər (ölçüldü:
    # 137-ci kataloqda 3 belə məhsul). Onda məhsul iki fərqli kart qazanır və
    # ikinci fayl birincinin üstünə yazılır - səssiz, çünki fayl adı
    # `p<product_id>.jpg`-dir. Məhsul da yalnız bir dəfə uduzmalıdır.
    assigned: set[int] = set()
    winners: list[Assignment] = []
    for claim in sorted(claims, key=lambda c: c.score, reverse=True):
        if claim.product_id in assigned:
            continue
        if claim.card_index in taken:
            # Eyni kartı iki məhsul istəyir. Xalı yüksək olan aldı; ikincisi
            # şəkilsiz qalır. Onu «ikinci seçiminə» göndərmirik: ikinci seçim
            # onsuz da yuxarıdakı 0.05 fərq yoxlamasından zəif çıxıb.
            why[claim.product_id] = "kart tutulub"
            continue
        taken.add(claim.card_index)
        assigned.add(claim.product_id)
        winners.append(claim)
        why.pop(claim.product_id, None)

    return winners, why


@dataclass
class CropReport:
    """Bir kataloq üçün nəticə - CLI bunu çap edir."""

    catalog_id: int
    pages: int = 0
    cards: int = 0
    matched: int = 0
    saved: int = 0
    # Atılanlar SƏBƏBƏ GÖRƏ ayrılır: «30 məhsul şəkilsiz qaldı» cümləsi
    # faydasızdır, «22-si qiymət uyğunluğu tapmadı» isə növbəti addımı göstərir.
    skipped: dict[str, int] = field(default_factory=dict)

    def as_line(self) -> str:
        atilan = ", ".join(f"{k}: {v}" for k, v in self.skipped.items() if v) or "yoxdur"
        return (
            f"kataloq {self.catalog_id}: {self.pages} səhifə, {self.cards} kart, "
            f"{self.matched} uyğunluq, {self.saved} şəkil (atıldı — {atilan})"
        )


def normalize(text: str) -> str:
    """Müqayisə üçün sadələşdirilmiş mətn: kiçik hərf, yalnız hərf və rəqəm."""
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def _grid_steps(boxes: list[tuple[int, int, int, int]], page: Image.Image) -> tuple[int, int]:
    """
    Kartlar şəbəkəsinin sütun və sıra addımı.

    Qonşu qiymət qutuları arasındakı MEDİAN məsafə götürülür - median, çünki
    səhifədə tək-tük böyük reklam kartı olur və orta qiyməti sürüşdürür.
    Kart bir dənədirsə addım hesablana bilmir; belə halda səhifənin öz
    ölçüsündən ehtiyat dəyər götürülür.
    """
    xs = sorted({(b[0] + b[2]) // 2 for b in boxes})
    ys = sorted({(b[1] + b[3]) // 2 for b in boxes})

    def step(values: list[int], fallback: int) -> int:
        gaps = [b - a for a, b in zip(values, values[1:]) if b - a > 5]
        return int(median(gaps)) if gaps else fallback

    return (
        step(xs, page.width // 3),
        step(ys, page.height // 4),
    )


def cell_box(
    price_box: tuple[int, int, int, int],
    col_step: int,
    row_step: int,
    page: Image.Image,
) -> tuple[int, int, int, int]:
    """
    Qiymət qutusundan kartın XANASINI hesablayır.

    NİSBƏTLƏR TƏXMİN DEYİL - REAL SƏHİFƏDƏN ÖLÇÜLÜB (Araz endirim jurnalı,
    səhifə 2, 776px enində render):

        məhsul adı  x=[305,390] y=[325,355]   <- qiymətin SOLUNDA
        qiymət qut. x=[455,510] y=[330,375]   <- lövbər
        məhsul şəkli x=[400,510] y=[380,455]  <- qiymətin ALTINDA
        sütun addımı 200, sıra addımı 160

    İLK VARİANT SƏHV İDİ: şəkil qiymətin ÜSTÜNDƏ sayılırdı və kəsilmiş
    fayllarda yalnız qiymət qutusu görünürdü. Kataloqa baxanda göründü ki,
    quruluş əksinədir - ad və qiymət yuxarıda, şəkil onların altındadır.

    NİYƏ TAM XANA, YALNIZ FOTO YOX? Sınandı və ölçüldü: yalnız foto zolağını
    kəsəndə məhsulun altı kəsilirdi (su qabılarının dibi, qələmlərin ucu),
    çünki fotonun səhifədəki yeri kartdan karta 10-15% sürüşür - qlyanslı
    kataloqda foto sərbəst yerləşdirilir, şəbəkəyə tam oturmur. Tam xana isə
    HƏMİŞƏ məhsulu bütöv saxlayır: içində ad və qiymət də qalır, yəni nəticə
    kiçik kataloq kartına oxşayır və istifadəçi onu tanıyır.
    """
    left = price_box[0] - int(col_step * 0.60)
    right = price_box[2] + int(col_step * 0.02)
    top = price_box[1] - int(row_step * 0.12)
    # Aşağı sərhəd fotonun tam altına qədər uzanır, amma növbəti sıranın
    # qiymət qutusuna toxunmur (o, ~1.0 addım aşağıdadır).
    bottom = price_box[1] + int(row_step * 0.97)

    # Səhifədən kənara çıxmaq PIL-də səssizcə boş sahə verir - kəsirik.
    return (
        max(0, left),
        max(0, top),
        min(page.width, right),
        min(page.height, bottom),
    )


# Kəsilmiş sahə BOŞ sayılır: boz çalarların standart kənarlaşması bundan
# kiçikdirsə, kadrda demək olar tək rəng var.
#
# REAL SƏHVDƏN ÇIXIB: ilk qaçışda bir neçə məhsulun şəkli tamamilə ağ çıxdı -
# kart səhifənin kənarında idi və xana boş sahəyə düşmüşdü. Ekranda bu, "şəkil
# yüklənmədi" kimi görünürdü. Placeholder həmin halda daha dürüstdür.
BLANK_STD = 12.0


def is_blank(image: Image.Image) -> bool:
    """Kadrda məhsul varmı? Tək rəngli sahə şəkil deyil."""
    from PIL import ImageStat

    stat = ImageStat.Stat(image.convert("L"))
    return stat.stddev[0] < BLANK_STD


def save_crop(page: Image.Image, box: tuple[int, int, int, int], name: str) -> str | None:
    """
    Sahəni kəsib `products/` qovluğuna yazır. Fayl adını qaytarır.

    Çox kiçik sahə şəkil deyil - ya səhifənin kənarıdır, ya da səhv
    koordinatdır. Belə faylı saxlamaq boş boz kvadrat göstərmək deməkdir.
    """
    if box[2] - box[0] < 40 or box[3] - box[1] < 40:
        return None

    crop = page.crop(box)
    if is_blank(crop):
        return None
    crop.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

    PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{name}.jpg"
    # JPEG: kataloq şəkli fotoqrafiyadır, PNG-də fayl 4-5 dəfə böyük olardı.
    crop.convert("RGB").save(PRODUCT_IMAGE_DIR / filename, "JPEG", quality=82)
    return filename


def catalog_pages(file_path: Path, max_pages: int = 20):
    """Kataloq faylını PIL şəkillərinə çevirir (PDF və ya adi şəkil)."""
    if file_path.suffix.lower() == ".pdf":
        from ingestion.ocr import pdf_pages_to_images

        # `layout_scale` işlədilir, `ocr_scale` yox: kart analizi məhz bu
        # miqyasda aparılır, yəni koordinatlar həmin şəkilə aiddir. Fərqli
        # miqyasda render etsək, qutular səhifəyə düşməzdi.
        yield from pdf_pages_to_images(file_path, max_pages, settings.layout_scale)
    else:
        with Image.open(file_path) as img:
            yield img.convert("RGB")


def image_url(image_path: str | None) -> str:
    """Bazadakı fayl adı -> brauzer ünvanı. Boşdursa placeholder."""
    if not image_path:
        return PLACEHOLDER_URL
    return f"{IMAGE_URL_PREFIX}/{image_path}"
