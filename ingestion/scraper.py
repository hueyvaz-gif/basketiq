"""
Kataloq scraper-i: market saytından endirim jurnalını avtomatik çəkir.

Ölçülmüş qərar (tools/check_source.py ilə yoxlanıb, 2026-09-07):

    | Market      | robots.txt | Səhifə       | Kataloq        |
    |-------------|------------|--------------|----------------|
    | OBA         | icazə ✓    | statik HTML  | 3 PDF, 4-44 səh|
    | Araz Market | icazə ✓    | statik HTML  | 1 PDF × 54 səh.|
    | Bravo       | QADAĞA ✗   | JS (ng-app)  | -              |
    | Bazarstore  | icazə ✓    | JS render    | link tapılmadı |

Niyə Selenium defolt deyil? Hər iki seçilmiş mənbənin kataloq linkləri adi
HTML-də görünür - `requests` + BeautifulSoup kifayətdir. Selenium hər çağırışda
brauzer qaldırır (~3-5 san) və serverdə ayrıca Chrome binary tələb edir.
Ondan yalnız statik yol BOŞ qayıdanda istifadə edirik (`use_selenium=True`) -
"əvvəlcə ucuz yolu sına" prinsipi, eynilə OCR-dakı kimi.

Niyə Bravo yoxdur? `robots.txt` qadağan edir. Texniki olaraq mümkün olsa da,
etik və hüquqi olaraq etmirik - README-dəki qaydaya sadiqik.
"""

import time
import urllib.parse as urlparse
import urllib.robotparser as robotparser
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

from app.config import settings
from ingestion.ingest import IngestError, find_by_source_url, ingest_bytes

PDF_EXT = (".pdf",)
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")

# Kataloq linkini adi menyu linkindən ayırmaq üçün açar sözlər
CATALOG_HINTS = (
    "katalog", "kataloq", "endirim", "kampan", "aksiya", "jurnal",
    "brosur", "catalog", "magazine", "discount",
)


class ScrapeError(Exception):
    pass


@dataclass(frozen=True)
class Source:
    """Bir market mənbəyi. Yeni market əlavə etmək = bura bir sətir yazmaq."""

    key: str
    store: str
    page_url: str
    note: str = ""


SOURCES: dict[str, Source] = {
    "oba": Source(
        key="oba",
        store="OBA",
        page_url="https://oba.az/endirim-jurnali/",
        note="Statik HTML, 3 PDF (4-44 səhifə) - sınaq üçün ən rahat mənbə",
    ),
    "araz": Source(
        key="araz",
        store="Araz Market",
        page_url="https://arazmarket.az/az/discount-magazine",
        note="Statik HTML, 1 PDF, 54 səhifə (~9 MB) - mütləq max_pages ilə çağır",
    ),
}


@dataclass
class ScrapeReport:
    source: str
    store: str
    page_url: str
    found: list[str] = field(default_factory=list)
    ingested: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    used_selenium: bool = False

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "store": self.store,
            "page_url": self.page_url,
            "found": self.found,
            "found_count": len(self.found),
            "ingested": self.ingested,
            "skipped": self.skipped,
            "errors": self.errors,
            "used_selenium": self.used_selenium,
        }


# ---------------------------------------------------------------- nəzakət qaydaları

_robots_cache: dict[str, robotparser.RobotFileParser | None] = {}
_last_request_at: float = 0.0


def robots_allows(url: str) -> bool:
    """
    robots.txt icazə verirmi? Host üzrə bir dəfə oxunub yadda saxlanılır.

    robots.txt oxunmasa (404, timeout) icazə verilmiş sayırıq - standart
    davranış budur. Qadağa yalnız AÇIQ yazılıbsa tətbiq olunur.
    """
    parts = urlparse.urlparse(url)
    host = f"{parts.scheme}://{parts.netloc}"

    if host not in _robots_cache:
        rp = robotparser.RobotFileParser()
        rp.set_url(f"{host}/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        _robots_cache[host] = rp

    rp = _robots_cache[host]
    if rp is None:
        return True
    return rp.can_fetch(settings.user_agent, url)


def _polite_wait() -> None:
    """İki sorğu arasında ən azı REQUEST_DELAY_SECONDS gözlə - serveri yükləmə."""
    global _last_request_at
    wait = settings.request_delay_seconds - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _headers() -> dict:
    return {"User-Agent": settings.user_agent}


# ---------------------------------------------------------------- yükləmə


def fetch_html(url: str, use_selenium: bool = False) -> tuple[str, bool]:
    """
    Səhifənin HTML-ini qaytarır: (html, selenium_işlədildi).

    Əvvəlcə requests - ucuz yol. `use_selenium=True` olsa və statik HTML-də
    kataloq linki tapılmasa, çağıran tərəf `fetch_html_selenium`-a keçir.
    """
    if not robots_allows(url):
        raise ScrapeError(f"robots.txt qadağan edir: {url}")

    _polite_wait()
    res = requests.get(url, headers=_headers(), timeout=settings.request_timeout_seconds)
    res.raise_for_status()
    return res.text, False


def fetch_html_selenium(url: str) -> str:
    """
    JS ilə render olunan səhifə üçün ehtiyat yol.

    Lazy import: selenium yalnız bu funksiya çağırılanda yüklənir, beləliklə
    Chrome quraşdırılmayan serverdə də layihənin qalanı işləyir.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    if not robots_allows(url):
        raise ScrapeError(f"robots.txt qadağan edir: {url}")

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument(f"--user-agent={settings.user_agent}")

    driver = webdriver.Chrome(options=opts)
    try:
        driver.set_page_load_timeout(settings.request_timeout_seconds)
        driver.get(url)
        # JS-in linkləri yerləşdirməsi üçün qısa gözləmə
        time.sleep(3)
        return driver.page_source
    finally:
        driver.quit()


def download(url: str, max_mb: int | None = None) -> bytes:
    """
    Faylı endirir. Ölçü limiti AXINLA yoxlanılır - 100 MB-lıq faylı əvvəlcə
    yaddaşa yığıb sonra "böyükdür" demək mənasızdır.
    """
    if not robots_allows(url):
        raise ScrapeError(f"robots.txt qadağan edir: {url}")

    limit = (max_mb or settings.max_upload_mb) * 1024 * 1024
    _polite_wait()

    with requests.get(
        url, headers=_headers(), timeout=settings.request_timeout_seconds, stream=True
    ) as res:
        res.raise_for_status()

        declared = res.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > limit:
            raise ScrapeError(
                f"Fayl çox böyükdür: {int(declared) / 1024 / 1024:.1f} MB "
                f"(limit {limit / 1024 / 1024:.0f} MB)"
            )

        chunks: list[bytes] = []
        total = 0
        for chunk in res.iter_content(chunk_size=256 * 1024):
            total += len(chunk)
            if total > limit:
                raise ScrapeError(f"Fayl limiti aşdı ({limit / 1024 / 1024:.0f} MB)")
            chunks.append(chunk)

    return b"".join(chunks)


# ---------------------------------------------------------------- link tapma


def find_catalog_links(html: str, page_url: str) -> list[str]:
    """
    Səhifədəki kataloq fayllarının linkləri.

    PDF-lər şərtsiz götürülür (endirim jurnalı demək olar həmişə PDF-dir).
    Şəkillər isə yalnız URL-ində "kataloq/endirim/aksiya" kimi söz varsa -
    əks halda saytın bütün loqoları və məhsul şəkilləri siyahıya düşərdi.
    """
    soup = BeautifulSoup(html, "lxml")
    pdfs: list[str] = []
    imgs: list[str] = []

    def add(bucket: list[str], url: str) -> None:
        if url not in bucket:
            bucket.append(url)

    for tag in soup.find_all(["a", "img", "iframe", "embed"]):
        raw = tag.get("href") or tag.get("src") or tag.get("data-src")
        if not raw:
            continue
        full = urlparse.urljoin(page_url, raw)
        path = urlparse.urlparse(full).path.lower()

        if path.endswith(PDF_EXT):
            add(pdfs, full)
        elif path.endswith(IMG_EXT) and any(h in full.lower() for h in CATALOG_HINTS):
            add(imgs, full)

    # PDF həmişə şəkildən üstündür: text layer şansı var, OCR-siz keçə bilər
    return pdfs + imgs


def filename_from_url(url: str) -> str:
    """URL-dən fayl adı. Adsız linkdə ('.../file/') 'catalog.pdf' qoyulur."""
    name = urlparse.unquote(urlparse.urlparse(url).path.rstrip("/").split("/")[-1])
    if not name or "." not in name:
        return "catalog.pdf"
    return name


# ---------------------------------------------------------------- əsas axın


def discover(source: Source, use_selenium: bool = False) -> tuple[list[str], bool]:
    """Mənbə səhifəsindən kataloq linklərini tapır: (linklər, selenium_işlədildi)."""
    html, _ = fetch_html(source.page_url)
    links = find_catalog_links(html, source.page_url)

    if links or not use_selenium:
        return links, False

    # Statik yol boş qayıtdı - indi bahalı yola keçirik
    html = fetch_html_selenium(source.page_url)
    return find_catalog_links(html, source.page_url), True


def scrape_source(
    key: str,
    max_files: int = 1,
    max_pages: int | None = 3,
    force_ocr: bool = False,
    psm: int | None = None,
    use_selenium: bool = False,
) -> ScrapeReport:
    """
    Bir mənbəni uçdan-uca çəkir: səhifə -> linklər -> endirmə -> OCR -> DB.

    max_pages=3 defolt: skan PDF-in hər səhifəsi GPU-suz maşında ~10-20 saniyə
    OCR deməkdir. Araz-ın 54 səhifəsi ~15 dəqiqə çəkərdi. Əvvəlcə 3 səhifə ilə
    nəticəni görürsən, sonra limiti qaldırırsan.
    """
    source = SOURCES.get(key)
    if source is None:
        raise ScrapeError(
            f"Naməlum mənbə: '{key}'. Mövcud: {', '.join(sorted(SOURCES))}"
        )

    report = ScrapeReport(source=source.key, store=source.store, page_url=source.page_url)

    try:
        links, used_selenium = discover(source, use_selenium=use_selenium)
    except Exception as e:
        report.errors.append(f"Səhifə açılmadı: {type(e).__name__}: {e}")
        return report

    report.found = links
    report.used_selenium = used_selenium

    if not links:
        report.errors.append(
            "Kataloq linki tapılmadı. Sayt quruluşunu dəyişmiş ola bilər - "
            "tools/check_source.py ilə yoxla."
        )
        return report

    for url in links[:max_files]:
        # 1. URL səviyyəsində təkrar yoxlaması - endirməmişdən ƏVVƏL
        seen = find_by_source_url(url)
        if seen:
            report.skipped.append(
                {"url": url, "catalog_id": seen["id"], "reason": "bu URL artıq çəkilib"}
            )
            continue

        # 2. Endir
        try:
            content = download(url)
        except Exception as e:
            report.errors.append(f"{url} -> {type(e).__name__}: {e}")
            continue

        # 3. Ortaq ingest zənciri (hash təkrarı burada tutulur)
        try:
            result = ingest_bytes(
                content=content,
                filename=filename_from_url(url),
                store=source.store,
                source_url=url,
                force_ocr=force_ocr,
                psm=psm,
                max_pages=max_pages,
            )
        except IngestError as e:
            report.errors.append(f"{url} -> {e.message}")
            continue

        if result.duplicate:
            report.skipped.append(
                {"url": url, "catalog_id": result.catalog_id, "reason": "eyni fayl (hash)"}
            )
        else:
            report.ingested.append(result.as_dict())

    return report
