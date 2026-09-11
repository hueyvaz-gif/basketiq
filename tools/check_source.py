"""
Mənbə yoxlayıcı.

İKİ REJİMİ VAR:

  1. TƏK URL (köhnə rejim, dəyişməyib) - bir kataloq səhifəsini yoxlayır:
         python tools/check_source.py https://example.az/kataloq
         python tools/check_source.py https://example.az/kataloq.pdf
     Sual: robots icazə verirmi, səhifə statikdirmi, PDF-in text layer-i varmı.

  2. MAĞAZA QATI (yeni) - onlayn mağazanın kateqoriya səhifəsini yoxlayır və
     hansı çəkmə pilləsinin işlədiyini ölçür:
         python tools/check_source.py --all
         python tools/check_source.py --store araz
         python tools/check_source.py --store bravo --selenium

NİYƏ İKİ QAT?
BasketIQ-un iki fərqli mənbəyi var və onlar qarışdırılmamalıdır:
  • həftəlik KATALOQ (PDF/şəkil) - "9.99 -> 5.99" İDDİASINI verir;
  • onlayn MAĞAZA (kateqoriya səhifələri) - məhsulun ADİ qiymətini verir.
İddianı yoxlamaq üçün ikincisi lazımdır - kataloqu yenə kataloqla təsdiqləmək
dairəvi məntiqdir. Bu skript ikinci qatın mümkünlüyünü ÖLÇÜR, fərz etmir.

PİLLƏ SIRASI (növbətiyə yalnız əvvəlki uğursuz olanda keçilir):
  1. JSON/XHR endpoint - sayt datanı API-dən çəkirsə, birbaşa `requests`.
     Ən sürətli və ən davamlı yol: səhifə dizaynı dəyişəndə qırılmır.
  2. requests + BeautifulSoup - qiymət HTML mətnində görünürsə.
  3. Selenium - yalnız 1 və 2 boş qayıdanda, açıq `--selenium` bayrağı ilə.

ROBOTS QAYDASI - BU SKRIPTDƏ SƏRTDİR:
`robots.txt` qadağan etdiyi URL ÇƏKİLMİR. Qadağanı keçmək üçün heç bir üsul
(User-Agent gizlətmə, proxy, "yalnız Selenium ilə açmaq") işlədilmir. Xüsusən:
səhifənin data ünvanı (`/api/`, `/_next/data/`) qadağandırsa, Selenium DA
işlədilmir - brauzer həmin ünvanları avtomatik çağırır, yəni "brauzerlə açmaq"
qadağanı texniki cəhətdən keçmək deməkdir. Bax `_selenium_allowed()`.
"""

import io
import re
import sys
import time
import urllib.parse as urlparse
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

# Windows konsolu bəzən cp1252-dir - Azərbaycan hərfləri onu qırır
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import settings  # noqa: E402
from ingestion.robots import RobotsRules, robots_url_for  # noqa: E402

HEADERS = {"User-Agent": settings.user_agent}
PDF_EXT = (".pdf",)
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")

# JS framework-lərin izləri - varsa səhifə çox güman dinamikdir
JS_MARKERS = ("__NUXT__", "__NEXT_DATA__", "ng-app", "data-reactroot", "vue-app")

# Qiymətin HTML-də HAZIR olduğunu göstərən nümunələr. Yalnız bunlardan biri
# tapılanda 2-ci pillə (BeautifulSoup) işlək sayılır.
PRICE_PATTERNS = (
    r"[0-9]+[.,][0-9]{2}\s*(?:₼|AZN|man\.?)\b",
    r'"price"\s*:\s*"?[0-9]',
    r'data-price\s*=\s*"[0-9]',
    r'itemprop\s*=\s*"price"',
)

# Səhifənin datanı hansı ünvandan çəkdiyini göstərən izlər (1-ci pillə üçün).
DATA_PATH_HINTS = ("/api/", "/graphql", "/_next/data/", "/wp-json/")

# Framework-in İZLƏRİ - `JS_MARKERS` kifayət etmir. Next.js-in app router-i
# `__NEXT_DATA__` yazmır; onun yeganə açıq izi asset yoludur (`/_next/...`).
# Bu siyahı olmasa Araz "framework deyil" sayılırdı və data qadağası
# Selenium qapısında işə düşmürdü.
FRAMEWORK_PATH_MARKERS = ("/_next/", "/_nuxt/", "/wp-content/", "/_astro/")

# Nəzakət: sorğular arasında ən azı bu qədər gözlənilir. `.env`-dəki dəyər
# daha böyükdürsə o götürülür - kiçikdirsə bu hədd qalır.
MIN_DELAY_SECONDS = 1.0

# Kateqoriya səhifəsi sayılmaq üçün minimum link sayı. Bundan azdırsa səhifə
# mağaza kataloqu deyil - baxım elanı, yönləndirmə və ya xəta səhifəsidir.
MIN_SHOP_LINKS = 5

_last_request_at = 0.0


def _throttle() -> None:
    """Sorğular arasında gecikmə. Skript nə qədər tələssə də saytı yormur."""
    global _last_request_at
    delay = max(MIN_DELAY_SECONDS, settings.request_delay_seconds)
    wait = delay - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def line(title: str) -> None:
    print(f"\n{'─' * 60}\n{title}\n{'─' * 60}")


# ------------------------------------------------------------------ robots.txt

_robots_cache: dict[str, RobotsRules | None] = {}


def _robots_for(url: str) -> tuple[RobotsRules | None, str]:
    """
    Host üzrə robots.txt-i bir dəfə oxuyur.

    Faylı ÖZ dürüst User-Agent-imizlə çəkirik: `urllib.robotparser.read()`
    özünü `Python-urllib/3.x` kimi təqdim edir və bir sıra sayt (ölçülüb:
    umico.az, bravosupermarket.az) həmin ada 403 qaytarır — nəticədə
    `Allow: /` yazan sayt "hər şey qadağan" kimi oxunurdu. Bu, qadağanı
    keçmək deyil, qadağanın həqiqi mətnini oxumaqdır; sorğularımızı da elə
    həmin ad ilə göndəririk, gizlətmə yoxdur.

    Qaydaların özünü `ingestion.robots` şərh edir (RFC 9309 — ən uzun
    uyğunluq qalib gəlir). Səbəb həmin modulun başında yazılıb.

    Status kodları:
      200      → qaydalar tətbiq olunur
      401/403  → sayt bizi açıq şəkildə istəmir → HAMISI QADAĞAN
      404/410  → robots.txt yoxdur → icazə var
      5xx/xəta → naməlum → `None` (çağıran "sənədsiz" kimi qeyd edir)
    """
    parts = urlparse.urlparse(url)
    host = f"{parts.scheme}://{parts.netloc}"
    robots_url = robots_url_for(url)

    if host not in _robots_cache:
        try:
            _throttle()
            res = requests.get(
                robots_url, headers=HEADERS, timeout=settings.request_timeout_seconds
            )
            if res.status_code in (401, 403):
                _robots_cache[host] = RobotsRules(disallow_all=True)
            elif res.status_code >= 400:
                _robots_cache[host] = RobotsRules(allow_all=True)
            else:
                if "charset" not in res.headers.get("Content-Type", "").lower():
                    res.encoding = res.apparent_encoding or "utf-8"
                _robots_cache[host] = RobotsRules.parse(res.text, settings.user_agent)
        except Exception:
            _robots_cache[host] = None
    return _robots_cache[host], robots_url


def robots_allows(url: str) -> bool:
    rules, _ = _robots_for(url)
    if rules is None:
        return True
    return rules.allows(url)


def check_robots(url: str) -> None:
    line("1. robots.txt")
    rules, robots_url = _robots_for(url)
    print(f"   {robots_url}")
    if rules is None:
        print("   robots.txt oxunmadı - ehtiyatlı ol, gecikmə ilə işlə")
        return
    allowed = rules.allows(url)
    print(f"   İcazə: {'BƏLİ ✓' if allowed else 'XEYR ✗ — bu mənbəni istifadə etmə'}")


# ------------------------------------------------------------------ HTTP

def fetch(url: str, *, quiet: bool = False) -> requests.Response | None:
    try:
        _throttle()
        r = requests.get(url, headers=HEADERS, timeout=settings.request_timeout_seconds)
        r.raise_for_status()
        return r
    except Exception as e:
        if not quiet:
            print(f"   Yüklənmədi: {type(e).__name__}: {e}")
        return None


# ------------------------------------------------------------------ mağaza qatı

@dataclass(frozen=True)
class Shop:
    """Bir marketin onlayn mağaza namizədi. Yeni market = bura bir sətir."""

    key: str
    store: str
    category_url: str
    note: str = ""


SHOPS: dict[str, Shop] = {
    "araz": Shop(
        key="araz",
        store="Araz",
        category_url="https://www.arazmarket.az/az/categories/quru-meyveler-2",
        note="Öz onlayn mağazası var (Next.js)",
    ),
    "bravo": Shop(
        key="bravo",
        store="Bravo",
        category_url="https://umico.az/categories/4497-dukan",
        note="Öz saytında mağaza yoxdur - onlayn satış Umico üzərindən",
    ),
    "bazarstore": Shop(
        key="bazarstore",
        store="Bazarstore",
        category_url="https://bazarstore.az/",
        note="Sayt namizədi",
    ),
}


@dataclass
class ShopProbe:
    """Bir mağaza namizədinin ölçülmüş nəticəsi. Fərziyyə saxlanılmır."""

    shop: Shop
    robots_ok: bool | None = None          # None = robots.txt oxunmadı
    robots_note: str = ""
    http_status: int | None = None
    html_bytes: int = 0
    text_chars: int = 0
    js_markers: list[str] = field(default_factory=list)
    price_hits: list[str] = field(default_factory=list)
    data_paths: list[str] = field(default_factory=list)
    data_paths_allowed: dict[str, bool] = field(default_factory=dict)
    blocked_hints: list[str] = field(default_factory=list)
    text_sample: str = ""                  # səhifənin ilk görünən sözləri
    link_count: int = 0                    # <a href> sayı
    tier: str = "?"                        # işləyən pillə
    reason: str = ""                       # niyə məhz bu pillə

    @property
    def is_client_rendered(self) -> bool:
        """
        Səhifə brauzerdə qurulurmu?

        İki əlamətdən biri kifayətdir: framework izi, və ya "böyük HTML, kiçik
        mətn" nisbəti (1.4 MB fayl, 634 simvol mətn = məzmun hələ gəlməyib).
        """
        if probe_markers := self.js_markers:
            return bool(probe_markers)
        return self.html_bytes > 50_000 and self.text_chars < 2_000

    @property
    def verdict(self) -> str:
        return f"{self.tier} — {self.reason}" if self.reason else self.tier


def _find_price_hits(html: str) -> list[str]:
    hits: list[str] = []
    for pattern in PRICE_PATTERNS:
        found = re.findall(pattern, html)
        hits.extend(found[:3])
    return hits[:6]


def _find_data_paths(html: str) -> list[str]:
    """Səhifənin datanı hansı ünvandan çəkdiyinə dair izlər."""
    return sorted({hint for hint in DATA_PATH_HINTS if hint in html})


def _selenium_allowed(probe: ShopProbe) -> tuple[bool, str]:
    """
    Selenium-a icazə varmı?

    Səhifənin ÖZÜ qadağandırsa - yox. Səhifə açıq, amma data ünvanı
    (`/api/`, `/_next/data/`) qadağandırsa - YENƏ YOX. Səbəb: brauzer səhifəni
    render edəndə həmin qadağan ünvanları özü çağırır. "Mən yalnız səhifəni
    açdım" deyib data qadağasını keçmək qadağanı pozmaqdır, sadəcə dolayı yolla.
    """
    if probe.robots_ok is False:
        return False, "səhifənin özü robots ilə qadağandır"
    if probe.blocked_hints and probe.is_client_rendered:
        return False, (
            f"səhifə JS ilə render olunur ({', '.join(probe.js_markers)}) və onun data "
            f"ünvanı qadağandır: {', '.join(probe.blocked_hints)}"
        )
    blocked = [p for p, ok in probe.data_paths_allowed.items() if not ok]
    if blocked:
        return False, f"data ünvanı qadağandır: {', '.join(blocked)}"
    return True, ""


def probe_shop(shop: Shop, *, use_selenium: bool = False) -> ShopProbe:
    """Bir mağaza namizədini pillə-pillə yoxlayır."""
    probe = ShopProbe(shop=shop)

    # --- robots (səhifənin özü) ---------------------------------------------
    rules, robots_url = _robots_for(shop.category_url)
    if rules is None:
        probe.robots_ok = None
        probe.robots_note = "robots.txt oxunmadı/yoxdur"
    else:
        probe.robots_ok = rules.allows(shop.category_url)
        probe.robots_note = "icazə ✓" if probe.robots_ok else "QADAĞA ✗"

    if probe.robots_ok is False:
        probe.tier = "YOX"
        probe.reason = "robots.txt qadağan edir - çəkilmir"
        return probe

    # --- səhifəni çək --------------------------------------------------------
    res = fetch(shop.category_url, quiet=True)
    if res is None:
        probe.tier = "YOX"
        probe.reason = "səhifə yüklənmədi"
        return probe

    probe.http_status = res.status_code
    # `Content-Type`-da charset yoxdursa requests latin-1 fərz edir və
    # Azərbaycan hərfləri korlanır. Məzmundan təxmin etmək düzgün nəticə verir.
    if "charset" not in res.headers.get("Content-Type", "").lower():
        res.encoding = res.apparent_encoding or "utf-8"
    html = res.text
    probe.html_bytes = len(res.content)

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    probe.text_chars = len(soup.get_text(strip=True))
    probe.text_sample = soup.get_text(" ", strip=True)[:160]
    probe.link_count = len(soup.find_all("a", href=True))

    probe.js_markers = [m for m in JS_MARKERS if m in html]
    probe.js_markers += [m for m in FRAMEWORK_PATH_MARKERS if m in html]
    probe.price_hits = _find_price_hits(html)
    probe.data_paths = _find_data_paths(html)

    # Data ünvanlarına robots baxışı. İKİ AYRI SİYAHI:
    #   • data_paths_allowed - səhifədə REAL görünən ünvanlar (1-ci pillənin şərti)
    #   • blocked_hints - bu hostda qadağan olunmuş STANDART data ünvanları.
    # İkincisi lazımdır, çünki Next.js/Nuxt səhifəsi datanı `/_next/data/` və ya
    # `/api/` ilə çəkir, amma bu ünvan ilk HTML-də görünmür - render zamanı
    # yaranır. Yalnız HTML-də görünənə baxsaq, qadağan ünvanı işlədən səhifəni
    # "təmiz" sayıb Selenium ilə açardıq və qadağanı dolayı yolla pozardıq.
    for path in probe.data_paths:
        probe.data_paths_allowed[path] = robots_allows(
            urlparse.urljoin(shop.category_url, path)
        )
    probe.blocked_hints = [
        hint
        for hint in DATA_PATH_HINTS
        if not robots_allows(urlparse.urljoin(shop.category_url, hint))
    ]

    # --- mağaza səhifəsidirmi? ----------------------------------------------
    # Kateqoriya səhifəsində onlarla link olur (məhsul, alt-kateqoriya, menyu).
    # Bir neçə link = bu, mağaza kataloqu deyil (baxım səhifəsi, yönləndirmə,
    # xəta). Açar sözlə təxmin etmirik - link sayı ölçülən faktdır.
    if probe.link_count < MIN_SHOP_LINKS:
        probe.tier = "YOX"
        probe.reason = (
            f"səhifədə cəmi {probe.link_count} link var - mağaza kataloqu deyil"
        )
        return probe

    # --- 2-ci pillə: qiymət HTML-də hazırdırmı? ------------------------------
    # (1-ci pillədən əvvəl yoxlanılır, çünki cavabı elə əldəki HTML-dədir;
    #  sıra pozulmur - aşağıdakı qərar blokunda 1-ci pillə yenə öndədir.)
    bs4_works = bool(probe.price_hits)

    # --- 1-ci pillə: JSON/XHR ------------------------------------------------
    allowed_data = [p for p, ok in probe.data_paths_allowed.items() if ok]
    blocked_data = [p for p, ok in probe.data_paths_allowed.items() if not ok]

    if allowed_data:
        probe.tier = "1 · JSON/XHR"
        probe.reason = f"data ünvanı açıqdır: {', '.join(allowed_data)}"
    elif bs4_works:
        probe.tier = "2 · BS4"
        probe.reason = f"qiymət HTML-də görünür ({probe.price_hits[0]!r})"
    elif blocked_data:
        probe.tier = "YOX"
        probe.reason = f"qiymət HTML-də yoxdur, data ünvanı qadağan: {', '.join(blocked_data)}"
    else:
        probe.tier = "3 · Selenium"
        probe.reason = "qiymət HTML-də yoxdur, açıq data ünvanı tapılmadı"

    # 3-cü pillənin icazəsi BAYRAQDAN ASILI DEYİL. `--selenium` yazılmasa belə
    # hökm indi verilir: qadağan varsa mənbə "YOX"-dur, "sınamamışıq" deyil.
    if probe.tier.startswith("3"):
        ok, why = _selenium_allowed(probe)
        if not ok:
            probe.tier = "YOX"
            probe.reason = f"Selenium da olmaz - {why}"

    # --- 3-cü pillə: yalnız açıq istənəndə və icazə varsa --------------------
    if probe.tier.startswith("3") and use_selenium:
        ok, why = _selenium_allowed(probe)
        if not ok:
            probe.reason = f"Selenium işlədilmədi - {why}"
        else:
            rendered = _render_with_selenium(shop.category_url)
            if rendered is None:
                probe.reason = "Selenium qurulmayıb (pip install selenium)"
            else:
                hits = _find_price_hits(rendered)
                if hits:
                    probe.price_hits = hits
                    probe.reason = f"yalnız render sonrası qiymət göründü ({hits[0]!r})"
                else:
                    probe.tier = "YOX"
                    probe.reason = "render sonrası da qiymət tapılmadı"

    return probe


def _render_with_selenium(url: str) -> str | None:
    """Səhifəni brauzerdə açıb render olunmuş HTML-i qaytarır. Yoxdursa None."""
    try:
        import selenium  # noqa: F401  (yalnız quraşdırılıbmı - yoxlama)
    except ImportError:
        return None
    from ingestion.browser import new_chrome

    driver = new_chrome()
    try:
        driver.get(url)
        time.sleep(5)  # render üçün - JS-in şəbəkə sorğusu var
        return driver.page_source
    finally:
        driver.quit()


def print_shop_report(probes: list[ShopProbe]) -> None:
    line("MAĞAZA QATI — ölçülmüş nəticə")
    print(f"   User-Agent : {settings.user_agent}")
    print(f"   Gecikmə    : {max(MIN_DELAY_SECONDS, settings.request_delay_seconds)} san\n")

    head = f"   {'Market':<12} {'robots':<10} {'HTML':>9} {'mətn':>7} {'qiymət':>7}  Pillə"
    print(head)
    print("   " + "─" * (len(head) - 3))
    for p in probes:
        robots = {True: "icazə ✓", False: "QADAĞA ✗", None: "yoxdur ?"}[p.robots_ok]
        price = "var" if p.price_hits else "yox"
        print(
            f"   {p.shop.store:<12} {robots:<10} {p.html_bytes:>9,} {p.text_chars:>7,} "
            f"{price:>7}  {p.tier}"
        )

    print("\n   Təfərrüat:")
    for p in probes:
        print(f"\n   • {p.shop.store} — {p.shop.category_url}")
        print(f"     {p.shop.note}")
        print(f"     robots     : {p.robots_note}")
        if p.http_status:
            print(f"     HTTP       : {p.http_status}")
        if p.js_markers:
            print(f"     JS izləri  : {', '.join(p.js_markers)}")
        if p.data_paths:
            for path, ok in p.data_paths_allowed.items():
                print(f"     data ünvanı: {path}  →  {'icazə ✓' if ok else 'QADAĞA ✗'}")
        if p.blocked_hints:
            print(f"     qadağan yol: {', '.join(p.blocked_hints)}")
        if p.link_count:
            print(f"     link sayı  : {p.link_count}")
        if p.text_sample:
            print(f"     mətn        : {p.text_sample!r}")
        print(f"     NƏTİCƏ     : {p.verdict}")


# ------------------------------------------------------------------ tək URL rejimi

def check_pdf(content: bytes) -> None:
    line("PDF analizi")
    try:
        from pypdf import PdfReader
    except ImportError:
        print("   pypdf quraşdırılmayıb: pip install pypdf")
        return

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as e:
        print(f"   PDF oxunmadı: {e}")
        return

    pages = len(reader.pages)
    text = ""
    for page in reader.pages[:3]:
        text += page.extract_text() or ""

    chars = len(text.strip())
    print(f"   Səhifə sayı: {pages}")
    print(f"   İlk 3 səhifədə mətn: {chars} simvol")

    if chars > 200:
        print("   NƏTİCƏ: ✓ TEXT LAYER VAR — pypdf kifayətdir, OCR lazım deyil (ideal mənbə)")
        print(f"\n   Nümunə:\n   {text.strip()[:300]!r}")
    else:
        print("   NƏTİCƏ: ⚠ SKAN PDF — pytesseract ilə OCR lazımdır")


def check_html(url: str, html: str) -> None:
    soup = BeautifulSoup(html, "lxml")

    line("2. Səhifə statikdirmi?")
    found_markers = [m for m in JS_MARKERS if m in html]
    body_text = len(soup.get_text(strip=True))
    print(f"   HTML ölçüsü: {len(html)} simvol, mətn: {body_text} simvol")
    if found_markers:
        print(f"   JS izləri: {', '.join(found_markers)}")
    if body_text < 500 or found_markers:
        print("   NƏTİCƏ: ⚠ Çox güman JS render edir → SELENIUM lazım ola bilər")
    else:
        print("   NƏTİCƏ: ✓ Statik görünür → BEAUTIFULSOUP kifayətdir")

    line("3. Kataloq linkləri")
    pdfs, imgs = set(), set()
    for a in soup.find_all("a", href=True):
        full = urlparse.urljoin(url, a["href"])
        low = full.lower().split("?")[0]
        if low.endswith(PDF_EXT):
            pdfs.add(full)
        elif low.endswith(IMG_EXT):
            imgs.add(full)
    for img in soup.find_all("img", src=True):
        full = urlparse.urljoin(url, img["src"])
        if any(k in full.lower() for k in ("katalog", "kataloq", "catalog", "endirim", "aksiya")):
            imgs.add(full)

    print(f"   PDF link: {len(pdfs)}")
    for u in list(pdfs)[:5]:
        print(f"      • {u}")
    print(f"   Şəkil link: {len(imgs)}")
    for u in list(imgs)[:5]:
        print(f"      • {u}")

    if not pdfs and not imgs:
        print("\n   ⚠ Heç nə tapılmadı. Səbəblər: JS ilə yüklənir, və ya link başqa səhifədədir.")
    elif pdfs:
        print(f"\n   → Növbəti addım: python tools/check_source.py {list(pdfs)[0]}")


def check_single_url(url: str) -> None:
    print(f"\nYoxlanılır: {url}")
    check_robots(url)

    if not robots_allows(url):
        print("\n   Dayanıldı: robots.txt qadağan edir, səhifə çəkilmir.")
        return

    res = fetch(url)
    if res is None:
        return

    ctype = res.headers.get("Content-Type", "").lower()
    print(f"\n   HTTP {res.status_code} | {ctype} | {len(res.content)} bayt")

    if "pdf" in ctype or url.lower().split("?")[0].endswith(".pdf"):
        check_pdf(res.content)
    elif "html" in ctype:
        check_html(url, res.text)
    elif "image" in ctype:
        line("Şəkil aşkarlandı")
        print("   NƏTİCƏ: ⚠ OCR yolu (pytesseract) lazımdır")
    else:
        print(f"   Naməlum tip: {ctype}")


# ------------------------------------------------------------------ CLI

def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        print(f"Qeydiyyatdan keçmiş mağazalar: {', '.join(sorted(SHOPS))}")
        sys.exit(1)

    use_selenium = "--selenium" in args
    args = [a for a in args if a != "--selenium"]

    if args and args[0] == "--all":
        probes = [probe_shop(shop, use_selenium=use_selenium) for shop in SHOPS.values()]
        print_shop_report(probes)
        return

    if args and args[0] == "--store":
        if len(args) < 2 or args[1] not in SHOPS:
            print(f"Mövcud mağazalar: {', '.join(sorted(SHOPS))}")
            sys.exit(1)
        probes = [probe_shop(SHOPS[args[1]], use_selenium=use_selenium)]
        print_shop_report(probes)
        return

    check_single_url(args[0])


if __name__ == "__main__":
    main()
