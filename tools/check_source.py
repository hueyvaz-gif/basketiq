"""
Mənbə yoxlayıcı — Həftə 1, Addım 1B.

Bir market səhifəsinin URL-ini verirsən, skript sənə deyir:
  1. robots.txt icazə verirmi?
  2. Səhifə statikdir, yoxsa JS render edir (Selenium lazımdırmı)?
  3. Səhifədə kataloq (PDF/şəkil) linkləri varmı?
  4. PDF-in "text layer"-i varmı (pypdf kifayətdir), yoxsa OCR lazımdır?

İstifadə:
    python tools/check_source.py https://example.az/kataloq
    python tools/check_source.py https://example.az/kataloq.pdf

Niyə bu skript? Çünki "hansı market uyğundur" sualına fərziyyə ilə yox,
real ölçü ilə cavab vermək lazımdır. Bu qərar bütün pipeline-ı müəyyən edir.
"""

import io
import sys
import urllib.parse as urlparse
import urllib.robotparser as robotparser

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

HEADERS = {"User-Agent": settings.user_agent}
PDF_EXT = (".pdf",)
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")

# JS framework-lərin izləri — varsa səhifə çox güman dinamikdir
JS_MARKERS = ("__NUXT__", "__NEXT_DATA__", "ng-app", "data-reactroot", "vue-app")


def line(title: str) -> None:
    print(f"\n{'─' * 60}\n{title}\n{'─' * 60}")


def check_robots(url: str) -> None:
    line("1. robots.txt")
    parts = urlparse.urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        allowed = rp.can_fetch(settings.user_agent, url)
        print(f"   {robots_url}")
        print(f"   İcazə: {'BƏLİ ✓' if allowed else 'XEYR ✗ — bu mənbəni istifadə etmə'}")
    except Exception as e:
        print(f"   robots.txt oxunmadı ({e}) — ehtiyatlı ol, gecikmə ilə işlə")


def fetch(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=settings.request_timeout_seconds)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"   Yüklənmədi: {type(e).__name__}: {e}")
        return None


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


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    url = sys.argv[1]
    print(f"\nYoxlanılır: {url}")
    check_robots(url)

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


if __name__ == "__main__":
    main()
