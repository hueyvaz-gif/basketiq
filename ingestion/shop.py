"""
MAĞAZA (SAYT) QATI — onlayn mağazadan gündəlik rəf qiyməti.

`scraper.py` KATALOQ (iddia) qatıdır: «9.99 → 5.99» vədini oxuyur. Bu modul
isə İKİNCİ qatdır — məhsulun bu gün mağazada neçəyə satıldığı. İki qat
qəsdən ayrıdır: kataloqun öz iddiasını yenə kataloqla təsdiqləmək dairəvi
məntiqdir (`app/db.py`, `price_snapshots` şərhi).

Ona görə bu modul `prices` cədvəlinə YAZMIR — onun yeri
`price_snapshots(source='site')`-dir.

ÖLÇÜLMÜŞ QƏRAR: NİYƏ WOLT? (2026-09-10)
=======================================
Bravo üçün üç kanal sınandı, ikisi ölü çıxdı:

    | Kanal                     | Nəticə                                    |
    |---------------------------|-------------------------------------------|
    | bravosupermarket.az       | Marketinq saytı. Selenium ilə render      |
    |                           | edildi: məhsul da, qiymət də YOXDUR       |
    |                           | (12 şəkil — hamısı loqo/ikon). PDF 0.     |
    | umico.az/categories/      | Selenium ilə render edildi: səhifə açıq   |
    | 4497-dukan                | «0 məhsul · uyğun məhsul yoxdur» yazır.   |
    |                           | Render problemi deyil — kateqoriya boşdur.|
    | umico.az/search?q=...     | robots.txt QADAĞAN edir (`Disallow: /*?*`)|
    |                           | — açılmadı.                               |
    | **wolt.com**              | **İŞLƏYİR**: 38 Bravo məkanı, tam         |
    |                           | kateqoriya ağacı, ad+qiymət+köhnə qiymət  |
    |                           | +ölçü+vahid qiymət+şəkil. robots icazə ✓  |

`logs/sources.md`-dəki köhnə qeyd Umico-nu «3-cü pillə: Selenium» kimi
işarələmişdi və «Selenium ilə real render ÖLÇÜLMƏYİB» yazırdı. İndi ölçüldü:
Selenium də kömək etmir, çünki problem render deyil, kateqoriyanın boş
olmasıdır. Wolt isə Bravonun ÖZ saytının «Onlayn market» linkinin göstərdiyi
rəsmi kanaldır.

QİYMƏTİN MƏNASI: Wolt çatdırılma platformasıdır, ona görə qiymət rəfdəki
qiymətdən fərqlənə bilər. Bu, `source='site'` sətri kimi yazılır və UI-da
kataloq iddiasından ayrı göstərilir — səhv təəssürat yaranmasın.

VİRTUALLAŞDIRMA TƏLƏSİ (ölçüldü)
================================
Wolt siyahısı virtualdır: kart ekrandan çıxanda məzmunu BOŞALIR. Səhifəni
sona sürüşdürüb sonra oxusan, `[data-test-id="ItemCard"]` 36 element tapır,
amma hamısının `innerText`-i boşdur — və səhv səssizdir (xəta yox, sadəcə
sıfır məhsul). Ona görə kiçik addımlarla sürüşdürüb HƏR addımda görünən
kartları yığırıq. Ölçüldü: bir kateqoriyadan 93 məhsul, 26 saniyə.
"""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from app.config import settings
from app.models import ExtractedProduct
from ingestion.normalize import canonical_key, to_base, unit_price as calc_unit_price
from app.stores import market_for
from ingestion.profiles import profile_for
from ingestion.scraper import _polite_wait, robots_allows

# ---------------------------------------------------------------- seçicilər
#
# Wolt-un `data-test-id` atributları qeyri-rəsmi API-dir: sinif adları
# (`s1jejqp3`) hər buraxılışda dəyişir, `data-test-id` isə sabit qalır.
# Sinif adına bağlansaydıq, kod növbəti deploy-da səssizcə sıfır məhsul
# qaytarardı.
CARD_SELECTOR = '[data-test-id="ItemCard"]'
CATEGORY_HREF = 'a[href*="/items/"]'

# Kartdan məhsul yığan JS. Yalnız MƏZMUNU OLAN kartlar götürülür:
# virtuallaşdırma səbəbindən boş kart normal haldır, xəta deyil.
HARVEST_JS = """
const out = [];
for (const card of document.querySelectorAll('[data-test-id="ItemCard"]')) {
  const link = card.querySelector('a[href*="itemid"]');
  if (!link) continue;
  const lines = card.innerText.split('\\n').map(s => s.trim()).filter(Boolean);
  if (!lines.length) continue;
  const img = card.querySelector('img');
  out.push({
    href: link.getAttribute('href'),
    lines: lines,
    image: img ? (img.currentSrc || img.src || '').split('?')[0] : null,
  });
}
return out;
"""

AT_BOTTOM_JS = (
    "return (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 200;"
)

# «AZN 1.38» və ya «~AZN 1.38». Wolt qırılmayan boşluq ( ) işlədir —
# adi `\s` onu tutur, amma `split()` ilə bölsək sətir iki yerə düşərdi.
PRICE_RE = re.compile(r"^~?\s*AZN\s*([\d]+(?:[.,]\d+)?)\s*$")
UNIT_PRICE_RE = re.compile(r"^~?\s*AZN\s*([\d]+(?:[.,]\d+)?)\s*/\s*(\S+)\s*$")
# «~1kg», «2.5kg», «500 q», «1L», «6 ədəd»
SIZE_RE = re.compile(
    r"^~?\s*(\d+(?:[.,]\d+)?)\s*(kg|kq|q|qr|g|gr|l|ml|ədəd|eded|pcs|dəst|dest)\s*$",
    re.IGNORECASE,
)
ITEM_ID_RE = re.compile(r"itemid-([0-9a-f]+)", re.IGNORECASE)

# Kartın üstündəki nişanlar — ad deyil, atılır.
BADGES = {"populyar", "yeni", "endirim", "popular", "new", "top"}

# Wolt ölçü vahidi → layihənin `SizeUnit` dəyərləri
UNIT_MAP = {
    "kg": "kg", "kq": "kg",
    "g": "g", "gr": "g", "q": "g", "qr": "g",
    "l": "l", "ml": "ml",
    "ədəd": "pcs", "eded": "pcs", "pcs": "pcs", "dəst": "pcs", "dest": "pcs",
}


class ShopError(Exception):
    pass


@dataclass
class ShopReport:
    """`ScrapeReport` ilə eyni forma — admin paneli ikisini eyni cür göstərir."""

    slug: str
    store: str
    shop_url: str
    categories: list[str] = field(default_factory=list)
    products: list[ExtractedProduct] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    saved: int = 0
    elapsed_seconds: float = 0.0

    def as_dict(self) -> dict:
        return {
            "slug": self.slug,
            "store": self.store,
            "shop_url": self.shop_url,
            "categories": self.categories,
            "category_count": len(self.categories),
            "found_count": len(self.products),
            "saved": self.saved,
            "skipped": self.skipped,
            "skipped_count": len(self.skipped),
            "errors": self.errors,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
        }


# ---------------------------------------------------------------- brauzer


@contextmanager
def _browser():
    """
    Headless Chrome — bir dəfə qaldırılır, bütün kateqoriyalar üçün işlədilir.

    Hər kateqoriyaya ayrıca brauzer qaldırsaydıq, 40 kateqoriya = 40 × ~4 san
    yalnız başlanğıca gedərdi. Lazy import: Chrome quraşdırılmayan serverdə
    layihənin qalanı işləməyə davam edir (`scraper.fetch_html_selenium` ilə
    eyni səbəb).
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--window-size=1400,1600")
    # Gizlətmə YOXDUR: robots.txt-i hansı adla oxuyuruqsa, səhifəni də
    # həmin adla açırıq.
    opts.add_argument(f"--user-agent={settings.user_agent}")

    driver = webdriver.Chrome(options=opts)
    try:
        driver.set_page_load_timeout(settings.request_timeout_seconds)
        yield driver
    finally:
        driver.quit()


def _open(driver, url: str, settle: float = 8.0) -> None:
    """Səhifəni açır: robots yoxlaması + nəzakət gecikməsi + JS üçün gözləmə."""
    if not robots_allows(url):
        raise ShopError(f"robots.txt qadağan edir: {url}")
    _polite_wait()
    driver.get(url)
    time.sleep(settle)


# ---------------------------------------------------------------- kəşf


def discover_categories(driver, shop_url: str) -> list[tuple[str, str]]:
    """
    Məkanın kateqoriya siyahısı: [(ad, ünvan), ...].

    NİYƏ «Bütün məhsullar» SƏHİFƏSİ DEYİL? O səhifə də işləyir, amma
    kateqoriya adını İTİRİRDİ — `products.category` boş qalardı və UI-dakı
    kateqoriya ikonları «digər»ə düşərdi. Kateqoriya-kateqoriya getmək
    həmin sahəni pulsuz verir.
    """
    _open(driver, shop_url)
    hrefs = driver.execute_script(
        """
        const seen = new Map();
        for (const a of document.querySelectorAll('a[href*="/items/"]')) {
          const href = a.getAttribute('href');
          const name = (a.innerText || '').trim();
          if (href && !seen.has(href)) seen.set(href, name);
        }
        return [...seen.entries()];
        """
    )
    # Linklər nisbi gəlir («/az/aze/baku/venue/...»), ona görə mənbə ünvanının
    # origin hissəsi ilə tamamlanır.
    parts = shop_url.split("/", 3)
    origin = "/".join(parts[:3])

    out: list[tuple[str, str]] = []
    for href, name in hrefs:
        full = href if href.startswith("http") else origin + href
        # «Bütün məhsullar» qəsdən ATILIR: digər kateqoriyaların cəmidir,
        # saxlasaq hər məhsul iki dəfə yığılardı.
        if full.rstrip("/").endswith("/items") or not name:
            continue
        out.append((name, full))
    return out


# ---------------------------------------------------------------- yığım


def harvest_category(driver, url: str, max_steps: int = 120) -> list[dict]:
    """
    Bir kateqoriyanın bütün məhsul kartları.

    Virtuallaşdırmaya görə addım-addım sürüşdürülür və HƏR addımda görünən
    kartlar yığılır (modul başlığındakı «virtuallaşdırma tələsi»). Açar
    `href`-dir: eyni məhsul bir neçə addımda görünür, dublikat olmamalıdır.
    """
    _open(driver, url, settle=7.0)

    seen: dict[str, dict] = {}
    stagnant = 0
    for _ in range(max_steps):
        before = len(seen)
        for row in driver.execute_script(HARVEST_JS):
            seen.setdefault(row["href"], row)

        driver.execute_script("window.scrollBy(0, 700);")
        time.sleep(0.9)

        for row in driver.execute_script(HARVEST_JS):
            seen.setdefault(row["href"], row)

        stagnant = stagnant + 1 if len(seen) == before else 0
        # ÜÇ ADDIM QAYDASI: yalnız «dibə çatdıq» kifayət deyil — lazy yükləmə
        # dibdə yeni sətir əlavə edə bilir. Üç dəfə üst-üstə heç nə
        # gəlmirsə, siyahı həqiqətən bitib.
        if stagnant >= 3 and driver.execute_script(AT_BOTTOM_JS):
            break

    return list(seen.values())


# ---------------------------------------------------------------- parse


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def parse_card(row: dict, category: str) -> ExtractedProduct | None:
    """
    Kart sətirlərini `ExtractedProduct`-a çevirir.

    ÖLÇÜLMÜŞ FORMAT (iki variant, `~` = təxmini çəki):

        endirimli : ['Populyar', '~AZN 0.85', 'AZN 0.99', 'Xiyar Melit 1kq',
                     '~1kg', 'AZN 0.85 / kq']
        endirimsiz: ['~AZN 4.99', 'Pomidor Çəhrayı 1kq', '~1kg',
                     'AZN 4.99 / kq']

    Sətirlərin SIRASINA bel bağlamırıq — hər sətir öz nümunəsi ilə tanınır.
    Sıraya güvənsək, nişan («Populyar») olan və olmayan kartlar fərqli
    yerlərdən oxunardı və səhv yalnız bəzi məhsullarda görünərdi.
    """
    lines = row.get("lines") or []
    prices: list[float] = []
    unit_from_card: float | None = None
    size_value = size_unit = None
    name_candidates: list[str] = []

    for line in lines:
        clean = line.replace(" ", " ").strip()

        m = UNIT_PRICE_RE.match(clean)
        if m:
            unit_from_card = _num(m.group(1))
            continue

        m = PRICE_RE.match(clean)
        if m:
            prices.append(_num(m.group(1)))
            continue

        m = SIZE_RE.match(clean)
        if m:
            size_value = _num(m.group(1))
            size_unit = UNIT_MAP.get(m.group(2).lower())
            continue

        if clean.lower() in BADGES:
            continue
        name_candidates.append(clean)

    if not prices or not name_candidates:
        return None

    # Ad: qalan sətirlərin ƏN UZUNU. Bəzi kartlarda ad iki sətrə bölünür
    # (marka + ad) və qısası markadır.
    name = max(name_candidates, key=len)

    # Birinci qiymət cari, ikincisi köhnədir. Tərsinə düşərsə (Wolt bəzən
    # köhnəni əvvəl yazır) böyüyü köhnə sayılır — qiymət heç vaxt öz
    # köhnəsindən baha ola bilməz.
    price = prices[0]
    old_price = None
    if len(prices) > 1:
        price, old_price = min(prices[0], prices[1]), max(prices[0], prices[1])
        if old_price <= price:
            old_price = None

    base_value, base_unit = to_base(size_value, size_unit)
    computed, _ = calc_unit_price(price, size_value, size_unit)
    # Wolt-un öz vahid qiyməti ÜSTÜNDÜR: çəki ilə satılan məhsulda («~2.5kg»)
    # ölçü təxminidir, Wolt isə real kq qiymətini yazır.
    final_unit = unit_from_card if unit_from_card is not None else computed

    return ExtractedProduct(
        name=name,
        brand=None,
        size_value=size_value,
        size_unit=size_unit,
        category=category or "digər",
        price=price,
        old_price=old_price,
        unit_price=final_unit,
        base_unit=base_unit,
        canonical_key=canonical_key(name, None, size_value, size_unit),
        # ŞƏFFAFLIQ: kartın orijinal mətni saxlanılır, eynilə OCR sətri kimi.
        raw_line=" | ".join(lines),
    )


# ---------------------------------------------------------------- əsas axın


def scrape_shop(
    slug: str,
    max_categories: int | None = None,
    max_products: int | None = None,
) -> ShopReport:
    """
    Marketin onlayn mağazasından bütün məhsulları çəkir.

    MARKET ADI PARAMETRDİR: funksiya Bravoya aid deyil. Yeni market üçün
    `profiles.py`-də `shop_url` yazmaq kifayətdir — bu funksiya dəyişmir.
    """
    profile = profile_for(slug)
    if profile is None:
        raise ShopError(f"Profil tapılmadı: {slug}")
    if not profile.shop_url:
        raise ShopError(
            f"«{slug}» üçün mağaza ünvanı yoxdur — `profiles.py`-də `shop_url` yaz"
        )

    # Görünən ad reyestrdən gəlir (`app/stores.py`) - profil onu saxlamır və
    # iki yerdə saxlanılsaydı, biri dəyişəndə digəri köhnə qalardı.
    market = market_for(profile.slug)
    started = time.monotonic()
    report = ShopReport(
        slug=profile.slug,
        store=market.name if market else profile.slug,
        shop_url=profile.shop_url,
    )

    with _browser() as driver:
        try:
            cats = discover_categories(driver, profile.shop_url)
        except Exception as e:  # noqa: BLE001 - səbəb hesabata yazılır
            raise ShopError(f"Kateqoriyalar oxunmadı: {type(e).__name__}: {e}") from e

        if max_categories:
            cats = cats[:max_categories]
        if not cats:
            report.errors.append("Kateqoriya tapılmadı - səhifə strukturu dəyişmiş ola bilər")
            report.elapsed_seconds = time.monotonic() - started
            return report

        görülən: set[str] = set()
        for name, url in cats:
            report.categories.append(name)
            try:
                rows = harvest_category(driver, url)
            except Exception as e:  # noqa: BLE001
                # BİR KATEQORİYA DÜŞSƏ, QALANI DAVAM EDİR: 40 kateqoriyanın
                # birində şəbəkə qırılması bütün çəkilişi ləğv etməməlidir.
                report.errors.append(f"{name}: {type(e).__name__}: {e}")
                continue

            for row in rows:
                item_id = ITEM_ID_RE.search(row.get("href") or "")
                key = item_id.group(1) if item_id else row.get("href")
                if key in görülən:
                    continue
                görülən.add(key)

                product = parse_card(row, name)
                if product is None:
                    report.skipped.append({"category": name, "lines": row.get("lines")})
                    continue
                report.products.append(product)

            if max_products and len(report.products) >= max_products:
                break

    report.elapsed_seconds = time.monotonic() - started
    return report
