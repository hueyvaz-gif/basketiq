"""
REAL MƏHSUL ŞƏKİLLƏRİ (M3) — marketin öz saytından, ehtiyatla.

PRİNSİP BİRDİR VƏ HƏR QƏRARIN ALTINDA DAYANIR:
**səhv şəkildənsə ikon yaxşıdır.** Şübhə varsa - təyin etmirik. Səbəb sadədir:
səhv şəkil YALAN danışır və istifadəçi ona inanır («deməli bu, həmin məhsuldur»),
ikon isə heç nə iddia etmir.

MƏNBƏ NECƏ TAPILDI (ölçüldü, fərz edilmədi):
    arazmarket.az/robots.txt  ->  Allow: /  ;  Disallow: /api/ /_next/ /admin/
    yəni /az/products/... səhifələri İCAZƏLİDİR
    sitemap-products-*.xml    ->  5000 azərbaycanca məhsul ünvanı
    məhsul səhifəsi           ->  <meta property="og:image"> əsas şəkli verir
    şəkil hostu (CDN)         ->  robots.txt: «Disallow:» (boş) = hər şeyə icazə

UYĞUNLAŞDIRMA İKİ MƏRHƏLƏDİR VƏ BİRİNCİSİ ŞƏBƏKƏSİZDİR:
    1. sitemap ünvanının SLUG-u ilə (eti-popkek-kakao-200-qr) - burada həm
       brend, həm ad, həm ölçü var. 188 məhsulu 5000 namizədlə müqayisə etmək
       bir neçə saniyədir və BİR sorğu da tələb etmir.
    2. yalnız qalib namizəd üçün səhifə açılır (og:image + kateqoriya yoxlaması).
Beləliklə 188 məhsul üçün 5000 yox, ~100 sorğu gedir.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from app.config import settings
from app.db import db_cursor, get_connection
from app.search_norm import fold

log = logging.getLogger(__name__)

# Layihə adı və əlaqə - sayt sahibi kimin gəldiyini görməlidir (3.3).
USER_AGENT = "BasketIQ-Student-Project/1.0 (educational; contact: groupf766@gmail.com)"

SITEMAP_INDEX = "https://www.arazmarket.az/sitemap.xml"
CATEGORY_SITEMAP = "https://www.arazmarket.az/sitemap-categories.xml"
# Media qovluğundadır (`settings.media_dir`) - Docker-də bazanın volume-u.
IMAGE_DIR = settings.media_dir / "product_images"
IMAGE_URL_PREFIX = "/static/product_images"

# Şəkil formatı: webp - eyni keyfiyyətdə PNG-dən 4-5 dəfə kiçikdir və
# kataloq səhifəsində onlarla şəkil eyni anda yüklənir.
IMAGE_SUFFIX = ".webp"

# Slug-da MƏNA DAŞIMAYAN parçalar. Sonundakı rəqəm (məsələn `-1`) saytın
# daxili identifikatorudur - ölçü kimi oxunmamalıdır.
_brend_keşi: frozenset[str] | None = None
_ümumi_söz_keşi: frozenset[str] | None = None

SLUG_STOPWORDS = {
    "ve", "ile", "ucun", "az", "en", "ru",
    # VAHİDLƏR AD DEYİL: «200 qr» slug-da iki token verir və «qr» hər ikinci
    # məhsulda təkrarlanır - onu ada saymaq balı süni şəkildə qaldırır.
    "q", "qr", "g", "gr", "kq", "kg", "ml", "l", "lt", "eded", "pcs",
}


# ============================================================================
# ÖLÇÜ (ən çox səhv buradan çıxır - ona görə skorun İÇİNDƏ deyil, AYRI qayda)
# ============================================================================

# Vahidlər əsas ölçüyə gətirilir: qram və millilitr.
_UNIT_BASE = {
    "q": ("g", 1), "qr": ("g", 1), "g": ("g", 1), "gr": ("g", 1),
    "kq": ("g", 1000), "kg": ("g", 1000),
    "ml": ("ml", 1), "l": ("ml", 1000), "lt": ("ml", 1000),
    "eded": ("pcs", 1), "pcs": ("pcs", 1),
}

_SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*-?\s*(kq|kg|qr|gr|ml|lt|q|g|l|eded|pcs)\b")


def parse_size(text: str | None) -> tuple[str, float] | None:
    """
    Mətndən ölçünü çıxarır: «200 qr» -> ('g', 200.0), «1.5 l» -> ('ml', 1500.0).

    NİYƏ AYRICA QAYDA, SKORUN HİSSƏSİ YOX? Ölçü uyğunsuzluğu ən çox rast
    gəlinən səhv mənbəyidir: «Sola günəbaxan yağı 1.8 L» ilə «Sola günəbaxan
    yağı 5 L» ad üzrə demək olar EYNİDİR - skor onları ayıra bilmir. Ölçü isə
    ayıra bilir və bu, YUMŞAQ deyil, SƏRT qayda olmalıdır.

    Tapılmasa `None` - yəni «ölçü bilinmir», «ölçü fərqlidir» deyil.
    """
    if not text:
        return None
    m = _SIZE_RE.search(fold(text))
    if not m:
        return None
    dəyər = float(m.group(1).replace(",", "."))
    baza, əmsal = _UNIT_BASE[m.group(2)]
    return baza, dəyər * əmsal


def size_conflict(a: tuple[str, float] | None, b: tuple[str, float] | None) -> bool:
    """
    İki ölçü BİR-BİRİNƏ ZİDDİRMİ?

    Yalnız HƏR İKİSİ məlum olanda müqayisə edilir: biri bilinmirsə, bu,
    ziddiyyət deyil - məlumatın yoxluğudur və rədd üçün əsas ola bilməz.
    Vahid növü fərqlidirsə (qram ilə litr) də müqayisə edilmir: eyni məhsul
    iki cür ölçülə bilər.
    """
    if not a or not b:
        return False
    if a[0] != b[0]:
        return False
    # 2% fərq yuvarlaqlaşdırmadır (500 q ilə 0.5 kq), fərq deyil.
    return abs(a[1] - b[1]) > max(a[1], b[1]) * 0.02


# ============================================================================
# UYĞUNLUQ BALI
# ============================================================================


def slug_tokens(slug: str) -> list[str]:
    """Ünvan slug-ını müqayisə tokenlərinə çevirir."""
    ad = slug.rsplit("/", 1)[-1]
    ad = re.sub(r"-\d+$", "", ad)          # saytın daxili id-si: `-1`, `-27`
    parçalar = [p for p in fold(ad).split("-") if p]
    return [p for p in parçalar if p not in SLUG_STOPWORDS and not p.isdigit()]


def product_tokens(name: str | None, brand: str | None) -> list[str]:
    """Bizim məhsulun müqayisə tokenləri (brend + ad)."""
    mətn = f"{brand or ''} {name or ''}".strip()
    return [p for p in fold(mətn).replace("-", " ").split() if p and not p.isdigit()]


def load_generic_words() -> frozenset[str]:
    """
    Saytın KATEQORIYA adlarındakı sözlər - «ümumi ad» lüğəti.

    NİYƏ KATEQORİYA SİTEMAP-I? Brendlərin siyahısı heç yerdə yoxdur, amma
    kateqoriya adları var: «süd», «şəkər tozu», «uşaq bezi». Kateqoriya
    adında OLMAYAN söz (richmond, borjomi, molfix) demək olar həmişə
    brenddir. Beləliklə brend lüğətini əl ilə saxlamırıq - onu saytın öz
    quruluşundan çıxarırıq.

    Şəbəkə xətası halında BOŞ çoxluq qayıdır: onda brend aşkarı yalnız öz
    bazamızdakı brendlərə söykənir - zəifləyir, amma sınmır.
    """
    global _ümumi_söz_keşi
    if _ümumi_söz_keşi is None:
        mətn = fetch(CATEGORY_SITEMAP)
        sözlər: set[str] = set()
        for url in re.findall(r"<loc>([^<]+)</loc>", mətn or ""):
            if "/az/categories/" in url:
                sözlər.update(slug_tokens(url))
        _ümumi_söz_keşi = frozenset(sözlər)
        log.info("ümumi söz lüğəti: %s", len(_ümumi_söz_keşi))
    return _ümumi_söz_keşi


def known_brands() -> frozenset[str]:
    """
    Öz bazamızdakı brend adları (qatlanmış).

    Brendlər ayrıca siyahı kimi saxlanmır - `products.brand` sütunu onsuz da
    doldurulur. İkinci siyahı yaratmaq onu köhnəlməyə məhkum etmək olardı.
    """
    global _brend_keşi
    if _brend_keşi is None:
        conn = get_connection()
        try:
            sətirlər = conn.execute(
                "SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != ''"
            ).fetchall()
        finally:
            conn.close()
        _brend_keşi = frozenset(
            f for f in (fold(r[0]) for r in sətirlər) if len(f) >= 3
        )
    return _brend_keşi


def foreign_brand_tokens(cand_tokens: list[str], ours: set[str]) -> set[str]:
    """
    Namizəddə olan, amma BİZDƏ olmayan brend görünüşlü sözlər.

    «Ümumi ad deyil + bizim sözlərimizdə yoxdur» = ehtimal ki, yad brend.
    Öz bazamızdakı brendlər də bu siyahıya əlavə olunur: onlar dəqiq
    brenddir, kateqoriya lüğətindən asılı deyil.
    """
    ümumi = load_generic_words()
    yad = set()
    for t in cand_tokens:
        if t in ours or len(t) < 3:
            continue
        if t not in ümumi or t in known_brands():
            yad.add(t)
    return yad


def brand_conflict(brand: str | None, cand_tokens: list[str]) -> bool:
    """
    SƏRT QAYDA 2: namizəd BAŞQA brendin məhsuludur.

    «Sola günəbaxan yağı» üçün «zateya-gunebaxan-yagi» sözlərin yarısını
    örtür - bal kifayət qədər yüksək çıxa bilər. Amma bu, səhv şüşənin
    şəklidir. Brend uyğunsuzluğu ona görə baldan ASILI OLMAYARAQ rədd edir.

    Brendimiz bilinmirsə qayda İŞLƏMİR: ziddiyyət yoxdur, məlumat yoxdur -
    o hal balın içində (aşağıdakı «təsdiqlənməmiş brend» cəzası ilə) həll olunur.
    """
    if not brand:
        return False
    bizim = fold(brand)
    if bizim in set(cand_tokens):
        return False
    return bool(foreign_brand_tokens(cand_tokens, {bizim}))


def match_score(our_tokens: list[str], cand_tokens: list[str], brand: str | None) -> float:
    """
    Çəkili token üst-üstə düşməsi (0..1).

    İKİ TƏRƏFLİ ÖLÇÜ: yalnız «bizim sözlərin neçəsi namizəddə var?» deyil,
    həm də əksi. Tək tərəfli ölçü uzun adları haqsız yerə mükafatlandırır -
    «süd» sorğusu «süd tozlu şokoladlı içki»yə tam uyğun görünərdi.

    AMMA İKİ TƏRƏF BƏRABƏR DEYİL - əvvəl harmonik orta işlədilirdi və bu,
    ÖLÇÜLƏN səhvlərə səbəb oldu:
      «Palmolive MAYE sabun» → `sabun-palmolive-sud-zeytun` (bərk sabun),
      «BLOOM ağardıcı» → `bloom-agardici-limon` (şüşədə «White Bello» yazılıb).
    Hər ikisində BİZİM sözümüz namizəddə yox idi - və hər ikisi 0.75 aldı,
    çünki harmonik orta «çatışmayan söz»ü «artıq söz»lə eyni cəzalandırır.

    HALBUKİ ONLAR EYNİ ŞEY DEYİL. Bizim sözümüz namizəddə yoxdursa,
    məhsulun NÖVÜ başqa ola bilər (maye ≠ bərk) - bu, təhlükəlidir.
    Namizəddə artıq söz varsa, o adətən dad/qablaşdırma təfərrüatıdır
    («keratin», «pendirli») - saytın adı sadəcə daha dəqiqdir.
    Ona görə əhatə əsas siqnaldır, dəqiqlik isə yalnız yumşaq amildir:
        ad_balı = əhatə × (0.6 + 0.4 × dəqiqlik)
    Tam əhatə heç vaxt 0.6-dan aşağı düşmür, yarımçıq əhatə isə 0.5-i
    keçə bilmir.

    BREND AYRICA ÇƏKİ ALIR (0.25), çünki o, məhsulu ən dəqiq ayıran sözdür.
    Amma tək başına kifayət deyil: eyni brendin onlarla məhsulu var.

    BRENDİMİZ YOXDURSA, ÇƏKİ AD-A QAYTARILIR. Əks halda brendsiz məhsul
    qazana bilməyəcəyi 0.25-i itirir: ideal ad uyğunluğu belə tavanda 0.75
    qalır və eşiyi keçmək demək olar mümkünsüz olur. Bu, uyğunluğun pisliyinə
    görə deyil, bizim bazamızda sətrin boş qalmasına görə cəza olardı.
    """
    if not our_tokens or not cand_tokens:
        return 0.0

    bizim, namizəd = set(our_tokens), set(cand_tokens)
    ortaq = bizim & namizəd
    if not ortaq:
        return 0.0

    əhatə = len(ortaq) / len(bizim)          # bizim sözlərin neçəsi tapıldı
    dəqiqlik = len(ortaq) / len(namizəd)     # namizədin neçə sözü işə yaradı
    ad_balı = əhatə * (0.6 + 0.4 * dəqiqlik)   # asimmetrik: bax sənədə

    if not brand:
        # Namizəddə də brend yoxdursa, yoxlanılacaq bir şey yoxdur - çəki
        # ada qaytarılır. Namizəddə brend VARSA, cəza qalır: onun bizimkinə
        # uyğun olub-olmadığını təsdiqləyə bilmirik.
        təsdiqlənməmiş = foreign_brand_tokens(cand_tokens, bizim)
        return round(0.75 * ad_balı if təsdiqlənməmiş else ad_balı, 4)

    brend_balı = 1.0 if fold(brand) in namizəd else 0.0
    return round(0.75 * ad_balı + 0.25 * brend_balı, 4)


@dataclass
class Candidate:
    url: str
    tokens: list[str] = field(default_factory=list)
    size: tuple[str, float] | None = None

    @classmethod
    def from_url(cls, url: str) -> "Candidate":
        return cls(url=url, tokens=slug_tokens(url), size=parse_size(url.rsplit("/", 1)[-1]))


@dataclass
class Match:
    candidate: Candidate | None
    score: float
    reason: str = ""


def pick_best(
    name: str | None,
    brand: str | None,
    size: tuple[str, float] | None,
    candidates: list[Candidate],
    min_confidence: float | None = None,
    ambiguity_gap: float | None = None,
) -> Match:
    """
    Namizədlərdən ƏN YAXŞISINI seçir - və ya rədd edir.

    RƏDD SƏBƏBLƏRİ AYRI-AYRI QAYTARILIR, çünki onlar manual baxış siyahısına
    düşür: «niyə bu məhsulun şəkli yoxdur?» sualının cavabı orada olmalıdır.
    """
    min_confidence = settings.product_image_min_confidence if min_confidence is None else min_confidence
    ambiguity_gap = settings.product_image_ambiguity_gap if ambiguity_gap is None else ambiguity_gap

    bizim = product_tokens(name, brand)
    if not bizim:
        return Match(None, 0.0, "adı yoxdur")

    bizim_çoxluq = set(bizim)
    xallı: list[tuple[float, Candidate]] = []
    for c in candidates:
        # SƏRT QAYDA 1: ölçü uyğunsuzluğu - skordan ASILI OLMAYARAQ rədd.
        if size_conflict(size, c.size):
            continue
        # SƏRT QAYDA 2: yad brend - bal nə olursa olsun.
        if brand_conflict(brand, c.tokens):
            continue
        bal = match_score(bizim, c.tokens, brand)
        if bal > 0:
            xallı.append((bal, c))

    if not xallı:
        return Match(None, 0.0, "uyğun namizəd yoxdur")

    xallı.sort(key=lambda cüt: cüt[0], reverse=True)
    ən_yaxşı, namizəd = xallı[0]

    if ən_yaxşı < min_confidence:
        return Match(None, ən_yaxşı, f"etibar aşağıdır ({ən_yaxşı:.2f} < {min_confidence})")

    # SƏRT QAYDA 4: birinci ilə ikinci arasında fərq çox kiçikdirsə, seçim
    # təsadüfə çevrilir.
    #
    # AMMA HƏR BƏRABƏRLİK TƏHLÜKƏ DEYİL - bunu ölçdük. Bərabər qalan 21
    # məhsulun hamısında namizədlər EYNİ MƏHSULUN variantları idi:
    #   «Zateya günəbaxan yağı» → 1.8 lt / 1 l / 500 ml
    #   «Molfix uşaq bezi»      → N6 / N5 / N2
    #   «Persil yuyucu toz»     → color / gül
    # Bizim adımızda variantı ayıran söz YOXDUR (vərəqədə sadəcə «Molfix uşaq
    # bezi» yazılıb), yəni hansını seçsək, bildiyimiz hər şeyə uyğundur -
    # şüşə də, paket də eyni görünür.
    #
    # Ona görə qayda belə dəqiqləşdirilir: bərabər qrupun HƏR üzvü bizim
    # BÜTÜN sözlərimizi ehtiva edirsə, bu, variant bərabərliyidir - seçim
    # təyinatlı şəkildə edilir. Üzvlərdən biri sözümüzü örtmürsə, onlar
    # müxtəlif məhsuldur («Tac peçenye» ↔ «tac-narşərab») - rədd qalır.
    if len(xallı) > 1 and (ən_yaxşı - xallı[1][0]) < ambiguity_gap:
        qrup = [c for bal, c in xallı if ən_yaxşı - bal < ambiguity_gap]
        if not all(bizim_çoxluq <= set(c.tokens) for c in qrup):
            return Match(
                None,
                ən_yaxşı,
                f"iki namizəd bərabərdir ({ən_yaxşı:.2f} / {xallı[1][0]:.2f})",
            )
        # TƏYİNATLI SEÇİM: ən qısa slug = ən az əlavə təyinli, yəni bazis
        # variant; bərabərlikdə ünvan özü sıralayır ki, nəticə hər işlətmədə
        # eyni olsun (təsadüfi şəkil dəyişməsi istifadəçini çaşdırar).
        namizəd = min(qrup, key=lambda c: (len(c.tokens), c.url))

    return Match(namizəd, ən_yaxşı)


# ============================================================================
# NƏZAKƏTLİ SORĞU (3.3)
# ============================================================================

_son_sorğu = 0.0


def _throttle() -> None:
    """Saniyədə bir sorğudan çox getmir - sayta yük salmaq bizim işimiz deyil."""
    global _son_sorğu
    keçən = time.monotonic() - _son_sorğu
    gecikmə = settings.product_image_delay_seconds - keçən
    if gecikmə > 0:
        time.sleep(gecikmə)
    _son_sorğu = time.monotonic()


def fetch(url: str, *, binary: bool = False, retries: int = 2):
    """
    Bir sorğu: nəzakət gecikməsi + timeout + eksponensial təkrar.

    XƏTA ATMIR, `None` QAYTARIR. Səbəb: bir məhsulun şəkli tapılmasa, proses
    DAYANMAMALIDIR - qalan 187 məhsul öz şansını almalıdır.
    """
    for cəhd in range(retries + 1):
        _throttle()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=settings.product_image_timeout) as r:
                if binary:
                    return r.headers, r.read(settings.product_image_max_bytes + 1)
                return r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            log.warning("sorğu uğursuz (%s/%s): %s -> %s", cəhd + 1, retries + 1, url, e)
            if cəhd < retries:
                time.sleep(2 ** cəhd)      # 1 san, sonra 2 san
    return None


def robots_allows(url: str) -> bool:
    """Mənbə saytın robots.txt-i bu ünvana icazə verirmi?"""
    from ingestion.robots import RobotsRules, robots_url_for

    mətn = fetch(robots_url_for(url), retries=1)
    if mətn is None:
        # Oxuya bilmiriksə ehtiyatlı davranırıq: icazə VERİLMİŞ saymırıq.
        return False
    return RobotsRules.parse(mətn, USER_AGENT).allows(url)


# ============================================================================
# NAMİZƏD SİYAHISI
# ============================================================================


def load_candidates(limit_pages: int = 3) -> list[Candidate]:
    """
    Sitemap-dan məhsul ünvanlarını yığır (yalnız azərbaycanca).

    ŞƏKİL ÇƏKİLİŞİNDƏN ƏVVƏL BİR DƏFƏ çağırılır: 5000 ünvan yaddaşda
    saxlanılır və 188 məhsulun hamısı onun üstündə uyğunlaşdırılır.
    """
    indeks = fetch(SITEMAP_INDEX)
    if not indeks:
        log.error("sitemap oxunmadı: %s", SITEMAP_INDEX)
        return []

    xəritələr = [
        u for u in re.findall(r"<loc>([^<]+)</loc>", indeks) if "sitemap-products" in u
    ][:limit_pages]

    namizədlər: list[Candidate] = []
    for xəritə in xəritələr:
        mətn = fetch(xəritə)
        if not mətn:
            continue
        for url in re.findall(r"<loc>([^<]+)</loc>", mətn):
            if "/az/products/" in url:
                namizədlər.append(Candidate.from_url(url))
    log.info("namizəd: %s", len(namizədlər))
    return namizədlər


def extract_image_url(html: str) -> str | None:
    """Məhsul səhifəsindən ƏSAS şəkli çıxarır (`og:image`)."""
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    return m.group(1) if m else None


def extract_category(html: str) -> str:
    """
    Səhifədən kateqoriya sözlərini yığır (breadcrumb + başlıqlar).

    Kateqoriya uyğunsuzluğu SƏRT rədd qaydasıdır, amma slug-da kateqoriya
    yoxdur - ona görə yoxlama səhifə açılandan SONRA aparılır. Əlavə sorğu
    tələb etmir: səhifəni onsuz da şəkil üçün açırıq.
    """
    parçalar = re.findall(r'"name"\s*:\s*"([^"]{2,40})"', html)
    return fold(" ".join(parçalar[:20]))


# Kateqoriyanın ZİDD sözləri: məhsul bu kateqoriyadadırsa, səhifədə bu
# sözlərdən biri görünərsə, uyğunluq şübhəlidir. Siyahı QISADIR və yalnız
# bir-birini istisna edən cütləri saxlayır - geniş siyahı yanlış rədd verər.
CATEGORY_CONFLICTS: dict[str, tuple[str, ...]] = {
    "süd məhsulları": ("temizlik", "gigiyena", "yuyucu"),
    "ət və balıq": ("temizlik", "gigiyena", "sirniyyat"),
    "təmizlik və gigiyena": ("sud", "et ve baliq", "sirniyyat", "meyve"),
    "şirniyyat": ("temizlik", "gigiyena", "yuyucu"),
    "içkilər": ("temizlik", "gigiyena", "yuyucu"),
}


def category_conflict(category: str | None, page_words: str) -> bool:
    """Səhifə bizim kateqoriyaya ZİDD sözlər daşıyırmı?"""
    if not category or not page_words:
        return False
    return any(söz in page_words for söz in CATEGORY_CONFLICTS.get(category, ()))


# ============================================================================
# ŞƏKLİN ENDİRİLMƏSİ VƏ KEŞİ (3.2) — HOTLINK YOX
# ============================================================================
#
# NİYƏ ENDİRİRİK, BİRBAŞA GÖSTƏRMİRİK? Üç səbəb:
#   1. hotlink kənar saytın serverinə bizim istifadəçilərimizin yükünü atır -
#      icazəsiz belə etmək düzgün deyil;
#   2. ünvan dəyişəndə şəkil SƏSSİZCƏ qırılır və səhifədə boş yer qalır;
#   3. mənbədəki fayl 1.6 MB PNG-dir; kataloq səhifəsində onlarla belə şəkil
#      istifadəçinin trafikini yeyərdi.
# Endirilmiş fayl 600px webp-ə çevrilir - eyni görüntü, onqat kiçik.


# Məhsul kətanın nə qədərini tutur. 0.86 = kənarda ~7% nəfəs payı.
# Pay BURADA, bir yerdə saxlanılır: CSS tərəfdə `padding` versəydik, o,
# yalnız plitənin ölçüsündən asılı olardı və fayldan-fayla dəyişən boşluğun
# üstünə gələrdi.
CONTENT_RATIO = 0.86

# Kənar piksel bu qədər açıqdırsa, fon sayılır. 244 ağı və çox açıq bozu
# tutur; məhsulun ağ hissəsini isə kəsmir, çünki qablaşdırmada tam düz və
# kadrın KƏNARINA çıxan ağ sahə praktiki olaraq olmur.
_BG_THRESHOLD = 244


def _content_box(img) -> tuple[int, int, int, int]:
    """
    Məhsulun çərçivəsi: kənardakı düz fon atılır.

    KƏSMƏK NİYƏ LAZIMDIR? Mənbə fotolarında məhsulun ətrafındakı boşluq
    fayldan-fayla müxtəlifdir. Kəsmədən normallaşdırsaq, «eyni kətan»
    yalnız FORMANI düzəldər, ÖLÇÜ fərqi qalar: biri kətanı doldurar,
    digəri ortada kiçik qalar.

    Fon tapılmasa (kadr bütövlükdə tünddürsə) və ya kəsik cırtdan çıxsa,
    bütöv şəkil qaytarılır - kəsmək məcburi deyil, sınmaq isə olmaz.
    """
    boz = img.convert("L")
    maska = boz.point(lambda p: 255 if p < _BG_THRESHOLD else 0)
    qutu = maska.getbbox()
    if not qutu:
        return (0, 0, img.width, img.height)
    if (qutu[2] - qutu[0]) < img.width * 0.1 or (qutu[3] - qutu[1]) < img.height * 0.1:
        return (0, 0, img.width, img.height)
    return qutu


def _to_square(img):
    """Məhsulu ağ KVADRAT kətanın ortasına, sabit payla oturdur."""
    from PIL import Image

    tərəf = settings.product_image_max_side
    kəsik = img.crop(_content_box(img))

    hədəf = int(tərəf * CONTENT_RATIO)
    # SÜNİ BÖYÜTMƏ YOXDUR: 200px fotonu 516px-ə dartmaq onu bulanıqlaşdırar.
    # Belə şəkil sadəcə kətanda daha kiçik qalır - bulanıq olmaqdansa kiçik.
    miqyas = min(hədəf / kəsik.width, hədəf / kəsik.height, 1.0)
    yeni = kəsik.resize(
        (max(1, int(kəsik.width * miqyas)), max(1, int(kəsik.height * miqyas))),
        Image.LANCZOS,
    )

    kətan = Image.new("RGB", (tərəf, tərəf), (255, 255, 255))
    kətan.paste(yeni, ((tərəf - yeni.width) // 2, (tərəf - yeni.height) // 2))
    return kətan


def _image_bytes_to_webp(data: bytes) -> tuple[bytes, int, int] | None:
    """
    Şəkli AĞ KVADRAT kətana normallaşdırır və webp qaytarır.
    -> (baytlar, en, hündürlük)

    NİYƏ NORMALLAŞDIRMA? ÖLÇÜLDÜ: mənbədən gələn 32 fotodan 31-i ENLİDİR
    (600×337, 600×333, 600×399), yalnız biri kvadratdır. Kartdakı plitə isə
    1:1-dir - `contain` ilə belə şəkil plitə hündürlüyünün cəmi ~56%-ni
    tutur. Nəticə şəbəkədə görünür: ikonun optik kütləsi SABİTDİR
    (44%×44%, mərkəzdə), fotolarınkı isə fayldan-fayla dəyişir və şəkilli
    kartlar bir-birindən fərqli «ağırlıqda» oxunur.

    LAYİHƏ BU PROBLEMİ BİR DƏFƏ HƏLL EDİB - market loqoları üçün
    (`tools/normalize_logos.py`): əvvəl kənardakı boşluq kəsilir, sonra
    şəkil eyni kətanın ortasına eyni payla oturdulur. Səbəb də eynidir:
    «`object-fit: contain` boşluğu da şəkil sayır».

    KƏTAN AĞDIR və bu, `.thumb.is-photo` fonunun ağ olmasını FƏRZİYYƏ
    olmaqdan çıxarıb FAKTA çevirir: mənbə fotolarının üçü (32-dən)
    qeyri-ağ fonludur, kətan onları da ağ üzərində birləşdirir.

    Tərəf 600px-dir: kartdakı plitə ən böyük halda 213px-dir, retina
    ekranda isə iki qat lazımdır. Daha böyük saxlamaq trafikdir.
    """
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as img:
            kətan = _to_square(img.convert("RGB"))
            çıxış = io.BytesIO()
            kətan.save(çıxış, format="WEBP", quality=82, method=4)
            return çıxış.getvalue(), kətan.width, kətan.height
    except Exception as e:      # zədəli/dəstəklənməyən fayl - proses dayanmır
        log.warning("şəkil çevrilmədi: %s", e)
        return None


def download_image(url: str) -> tuple[str, str, int, int] | None:
    """
    Şəkli endirir, yoxlayır, çevirir və saxlayır.
    -> (fayl_adı, image_hash, en, hündürlük)

    FAYL ADI MƏNBƏ ÜNVANININ HASH-IDİR: eyni şəkil iki məhsula uyğun gəlsə,
    ikinci dəfə endirilmir (dedupe) və disk boş yerə dolmur.
    """
    nəticə = fetch(url, binary=True)
    if not nəticə:
        return None
    headers, data = nəticə

    # SƏRT YOXLAMALAR - kənardan gələn fayla inanmırıq.
    tip = (headers.get("Content-Type") or "").lower()
    if not tip.startswith("image/"):
        log.warning("şəkil deyil (%s): %s", tip, url)
        return None
    if len(data) > settings.product_image_max_bytes:
        log.warning("şəkil %s baytdır, hədd %s: %s", len(data),
                    settings.product_image_max_bytes, url)
        return None

    image_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    fayl = IMAGE_DIR / f"{image_hash}{IMAGE_SUFFIX}"

    if fayl.exists():           # DEDUPE: eyni ünvan artıq endirilib
        from PIL import Image
        with Image.open(fayl) as var:
            return fayl.name, image_hash, var.width, var.height

    çevrilmiş = _image_bytes_to_webp(data)
    if çevrilmiş is None:
        return None
    webp, en, hündürlük = çevrilmiş

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    fayl.write_bytes(webp)
    return fayl.name, image_hash, en, hündürlük


# ============================================================================
# BAZA QATI
# ============================================================================

# Təkrar cəhd qaydaları (3.4). Rəqəmlər sabitdir və səbəbləri var:
RETRY_FAILED_DAYS = 7      # sayt cavab vermədi - həftədə bir yenidən sına
RECHECK_OK_DAYS = 30       # şəkil var - ayda bir kifayətdir


def _existing(conn, product_id: int):
    return conn.execute(
        "SELECT * FROM product_images WHERE product_id = ?", (product_id,)
    ).fetchone()


def needs_fetch(row, today: str | None = None) -> bool:
    """
    Bu məhsul üçün indi cəhd etmək lazımdırmı?

    ÜÇ FƏRQLİ CAVAB, ÜÇ FƏRQLİ SƏBƏB:
      · sətir yoxdur          -> bəli, heç vaxt sınanmayıb
      · manual = 1            -> XEYR, insan qərarı maşından üstündür (3.6)
      · rejected              -> XEYR, uyğunluq zəif idi; təkrar eyni nəticəni
                                 verəcək. Manual siyahıda gözləyir.
      · failed + 7 gün keçib  -> bəli, sayt bərpa oluna bilər
      · ok + 30 gün keçib     -> bəli, şəkil dəyişmiş ola bilər
    """
    from datetime import datetime, timedelta

    if row is None:
        return True
    if row["manual"]:
        return False
    if row["status"] == "rejected":
        return False

    try:
        çəkilib = datetime.fromisoformat(row["fetched_at"])
    except (TypeError, ValueError):
        return True

    indi = datetime.fromisoformat(today) if today else datetime.now()
    hədd = RETRY_FAILED_DAYS if row["status"] == "failed" else RECHECK_OK_DAYS
    return indi - çəkilib >= timedelta(days=hədd)


def save_result(
    product_id: int,
    *,
    status: str,
    image_path: str | None = None,
    source_url: str | None = None,
    confidence: float | None = None,
    image_hash: str | None = None,
    width: int | None = None,
    height: int | None = None,
    note: str | None = None,
    manual: bool = False,
) -> None:
    """
    Nəticəni yazır. MANUAL SƏTRİN ÜSTÜNDƏN AVTOMATİKA YAZMIR (3.6).

    `attempts` artır: «neçə dəfə sınadıq?» sualı hesabatda lazımdır - eyni
    məhsul üçün onlarla uğursuz cəhd varsa, problem uyğunlaşdırmada deyil,
    mənbədədir.
    """
    with db_cursor() as cur:
        cur.execute("SELECT id, manual, attempts FROM product_images WHERE product_id = ?",
                    (product_id,))
        mövcud = cur.fetchone()

        if mövcud and mövcud["manual"] and not manual:
            return      # insan qərarı qorunur

        cəhd = (mövcud["attempts"] if mövcud else 0) + 1
        cur.execute(
            "INSERT INTO product_images (product_id, image_path, source_url, confidence, "
            "                            image_hash, width, height, status, attempts, "
            "                            manual, note, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(product_id) DO UPDATE SET "
            "  image_path = excluded.image_path, source_url = excluded.source_url, "
            "  confidence = excluded.confidence, image_hash = excluded.image_hash, "
            "  width = excluded.width, height = excluded.height, "
            "  status = excluded.status, attempts = excluded.attempts, "
            "  manual = excluded.manual, note = excluded.note, "
            "  fetched_at = excluded.fetched_at",
            (product_id, image_path, source_url, confidence, image_hash,
             width, height, status, cəhd, int(manual), note),
        )


# ============================================================================
# ƏSAS AXIN (3.4)
# ============================================================================


def products_needing_images(limit: int | None = None) -> list[dict]:
    """
    Şəkil çəkilməli məhsullar: yalnız qiyməti olanlar.

    QİYMƏTSİZ MƏHSULA ŞƏKİL LAZIM DEYİL: o, heç bir siyahıda görünmür -
    şəkil çəkmək boş yerə sorğu deməkdir.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT p.id, p.name, p.brand, p.category, p.size_value, p.size_unit "
            "FROM products p JOIN prices pr ON pr.product_id = p.id "
            "GROUP BY p.id ORDER BY COUNT(pr.id) DESC"
        ).fetchall()

        çəkiləcək = []
        for row in rows:
            mövcud = _existing(conn, row["id"])
            if needs_fetch(mövcud):
                çəkiləcək.append(dict(row))
            if limit and len(çəkiləcək) >= limit:
                break
        return çəkiləcək
    finally:
        conn.close()


def _our_size(row: dict) -> tuple[str, float] | None:
    """Bizim məhsulun ölçüsü - `products` cədvəlindəki sütunlardan."""
    if row.get("size_value") and row.get("size_unit"):
        return parse_size(f"{row['size_value']} {row['size_unit']}")
    return parse_size(row.get("name"))


def assign_images(limit: int | None = None, dry_run: bool = False) -> dict:
    """
    Uçdan-uca: namizədlər -> uyğunlaşdırma -> səhifə -> şəkil -> baza.

    XƏTA PROSESİ DAYANDIRMIR (3.3): bir məhsul üçün sayt cavab verməsə,
    həmin sətir `failed` yazılır və növbəti məhsula keçilir. 188 məhsulun
    biri üzündən qalan 187-si şansını itirməməlidir.
    """
    hesabat = {"baxılan": 0, "ok": 0, "rejected": 0, "failed": 0, "manual_siyahı": []}

    if not robots_allows("https://www.arazmarket.az/az/products/"):
        log.error("robots.txt icazə vermir - çəkiliş dayandırıldı")
        hesabat["xəta"] = "robots.txt icazə vermir"
        return hesabat

    namizədlər = load_candidates()
    if not namizədlər:
        hesabat["xəta"] = "namizəd siyahısı boşdur"
        return hesabat

    for məhsul in products_needing_images(limit):
        hesabat["baxılan"] += 1
        uyğunluq = pick_best(
            məhsul["name"], məhsul["brand"], _our_size(məhsul), namizədlər
        )

        if uyğunluq.candidate is None:
            hesabat["rejected"] += 1
            hesabat["manual_siyahı"].append(
                {"product_id": məhsul["id"], "ad": məhsul["name"],
                 "bal": uyğunluq.score, "səbəb": uyğunluq.reason}
            )
            if not dry_run:
                save_result(məhsul["id"], status="rejected",
                            confidence=uyğunluq.score, note=uyğunluq.reason)
            continue

        if dry_run:
            hesabat["ok"] += 1
            continue

        səhifə = fetch(uyğunluq.candidate.url)
        if not səhifə:
            hesabat["failed"] += 1
            save_result(məhsul["id"], status="failed", source_url=uyğunluq.candidate.url,
                        confidence=uyğunluq.score, note="səhifə açılmadı")
            continue

        # SƏRT QAYDA 3: kateqoriya uyğunsuzluğu (səhifə açılandan sonra
        # yoxlanılır - slug-da kateqoriya yoxdur).
        if category_conflict(məhsul["category"], extract_category(səhifə)):
            hesabat["rejected"] += 1
            səbəb = f"kateqoriya uyğunsuzluğu ({məhsul['category']})"
            hesabat["manual_siyahı"].append(
                {"product_id": məhsul["id"], "ad": məhsul["name"],
                 "bal": uyğunluq.score, "səbəb": səbəb}
            )
            save_result(məhsul["id"], status="rejected", source_url=uyğunluq.candidate.url,
                        confidence=uyğunluq.score, note=səbəb)
            continue

        şəkil_url = extract_image_url(səhifə)
        if not şəkil_url:
            hesabat["failed"] += 1
            save_result(məhsul["id"], status="failed", source_url=uyğunluq.candidate.url,
                        confidence=uyğunluq.score, note="səhifədə şəkil yoxdur")
            continue

        endirilən = download_image(şəkil_url)
        if not endirilən:
            hesabat["failed"] += 1
            save_result(məhsul["id"], status="failed", source_url=şəkil_url,
                        confidence=uyğunluq.score, note="şəkil endirilmədi")
            continue

        fayl, image_hash, en, hündürlük = endirilən
        save_result(məhsul["id"], status="ok", image_path=fayl, source_url=şəkil_url,
                    confidence=uyğunluq.score, image_hash=image_hash,
                    width=en, height=hündürlük)
        hesabat["ok"] += 1

    return hesabat


# ============================================================================
# HESABAT VƏ MANUAL İDARƏ (3.6)
# ============================================================================


def coverage_report(worst: int = 20) -> dict:
    """
    «Neçə məhsulda şəkil var?» sualının bir yerdə cavabı.

    ƏN AŞAĞI ETİBARLI UYĞUNLUQLAR AYRICA VERİLİR: səhv şəkil axtarmağa
    məhz oradan başlamaq lazımdır - eşiyi yüksəltmək qərarı da o siyahıya
    baxaraq verilir.
    """
    conn = get_connection()
    try:
        cəmi = conn.execute(
            "SELECT COUNT(DISTINCT p.id) FROM products p JOIN prices pr ON pr.product_id = p.id"
        ).fetchone()[0]

        vəziyyət = dict(
            conn.execute(
                "SELECT status, COUNT(*) FROM product_images GROUP BY status"
            ).fetchall()
        )
        orta = conn.execute(
            "SELECT AVG(confidence) FROM product_images WHERE status = 'ok'"
        ).fetchone()[0]

        ən_zəif = conn.execute(
            "SELECT pi.product_id, p.name, p.brand, pi.confidence, pi.source_url "
            "FROM product_images pi JOIN products p ON p.id = pi.product_id "
            "WHERE pi.status = 'ok' ORDER BY pi.confidence ASC LIMIT ?",
            (worst,),
        ).fetchall()

        baxış = conn.execute(
            "SELECT pi.product_id, p.name, pi.confidence, pi.note "
            "FROM product_images pi JOIN products p ON p.id = pi.product_id "
            "WHERE pi.status = 'rejected' ORDER BY pi.confidence DESC LIMIT 50"
        ).fetchall()
    finally:
        conn.close()

    şəkilli = vəziyyət.get("ok", 0)
    return {
        "məhsul_cəmi": cəmi,
        "şəkilli": şəkilli,
        "əhatə_faizi": round(şəkilli / cəmi * 100, 1) if cəmi else 0.0,
        "rədd": vəziyyət.get("rejected", 0),
        "uğursuz": vəziyyət.get("failed", 0),
        "orta_etibar": round(orta, 3) if orta else None,
        "ən_zəif": [dict(r) for r in ən_zəif],
        "manual_baxış": [dict(r) for r in baxış],
    }


def set_manual_image(product_id: int, source_url: str) -> bool:
    """
    Əl ilə şəkil təyin edir. Avtomatika bu sətrin üstündən YAZMIR (3.6).

    Ünvan yenə də endirilir və yoxlanılır: «əl ilə» o demək deyil ki, kənar
    fayla gözübağlı inanırıq - ölçü həddi və content-type yoxlaması qalır.
    """
    endirilən = download_image(source_url)
    if not endirilən:
        return False
    fayl, image_hash, en, hündürlük = endirilən
    save_result(product_id, status="ok", image_path=fayl, source_url=source_url,
                confidence=1.0, image_hash=image_hash, width=en, height=hündürlük,
                note="əl ilə təyin edildi", manual=True)
    return True


def reject_image(product_id: int, note: str = "əl ilə rədd edildi") -> None:
    """Səhv şəkli rədd edir - avtomatika onu bir daha təyin etməyəcək."""
    save_result(product_id, status="rejected", note=note, manual=True)


def photo_map(conn=None) -> dict[int, dict]:
    """
    Şəkli olan məhsullar: `{product_id: {"url", "w", "h"}}`.

    ÖLÇÜLƏR DƏ BURADADIR, ayrı sorğuda yox: `<img>` teqi ünvanı və ölçünü
    birlikdə istəyir, iki ayrı xəritə isə çağıran tərəfdə iki lokal dəyişən
    və iki sorğu demək olardı.

    NİYƏ XƏRİTƏ, HƏR SƏTİR ÜÇÜN AYRI SORĞU YOX: kataloq funksiyaları onsuz da
    onlarla sətir qaytarır - hər birinə bir SELECT vurmaq N+1 olardı.
    Cədvəl kiçikdir (məhsul sayı qədər), bütövlükdə bir dəfə oxunur.

    KEŞ YOXDUR: gündəlik çəkiliş AYRI PROSESDƏ işləyir, veb prosesin keşi
    isə yenilənməzdi - istifadəçi yeni şəkli serveri yenidən başlatmayana
    qədər görməzdi. Bir kiçik SELECT bu riskə dəyməz.

    AÇIQ BAĞLANTI VERİLƏ BİLƏR: çağıran tərəf onsuz da bazanı açıb (kataloq
    sorğusu üçün). Ölçüldü: öz bağlantısını açmaq 3.09 ms-dir və bunun
    demək olar hamısı AÇILIŞDIR - `/api/catalog/search` cavabının (13 ms)
    dörddə biri. Hazır bağlantı ilə bu xərc sıfıra düşür.
    """
    öz_bağlantısı = conn is None
    conn = conn or get_connection()
    try:
        sətirlər = conn.execute(
            "SELECT product_id, image_path, width, height FROM product_images "
            "WHERE status = 'ok' AND image_path IS NOT NULL"
        ).fetchall()
    finally:
        if öz_bağlantısı:
            conn.close()
    return {
        r["product_id"]: {
            "url": f"{IMAGE_URL_PREFIX}/{r['image_path']}",
            "w": r["width"],
            "h": r["height"],
        }
        for r in sətirlər
    }


def image_url_for(image_path: str | None) -> str | None:
    """Bazadakı fayl adı -> brauzer ünvanı."""
    return f"{IMAGE_URL_PREFIX}/{image_path}" if image_path else None
