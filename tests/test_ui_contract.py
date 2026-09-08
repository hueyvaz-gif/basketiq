"""
Backend ilə frontend arasındakı SƏSSİZ müqavilələr.

Bu testlərin hamısı bir növ səhvi tutur: heç bir xəta atmayan, amma UI-ı
gizlicə kasıblaşdıran uyğunsuzluqlar.

Nümunə: `app/models.py`-yə yeni kateqoriya ("dondurulmuş məhsullar") əlavə
olunur. Backend onu qaytarır, frontend isə xəritədə tapmayıb hamısına eyni
"paket" ikonu verir. Səhifə işləyir, test keçir, heç kim bilmir - sadəcə
məhsul ikonları mənasını itirir. Aşağıdakı test məhz bunu tutur.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CATEGORIES

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"

client = TestClient(app)


def read_static(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


# --------------------------------------------------------- kateqoriya -> ikon


def parse_category_icons() -> dict[str, str]:
    """`app.js`-dəki CATEGORY_ICON xəritəsini oxuyur."""
    source = read_static("app.js")
    block = re.search(r"const CATEGORY_ICON = \{(.*?)\n\};", source, re.S)
    assert block, "CATEGORY_ICON xəritəsi app.js-də tapılmadı"
    return dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', block.group(1)))


def test_hər_kateqoriyanın_ikonu_var():
    """
    CATEGORIES siyahısı ilə frontend xəritəsi tam üst-üstə düşməlidir.

    Bir tərəfə element əlavə edib digərini unutmaq ən asan səhvdir və
    heç bir yerdə xəta vermir.
    """
    mapping = parse_category_icons()
    assert set(mapping) == set(CATEGORIES), (
        f"uyğunsuzluq — yalnız backend-də: {sorted(set(CATEGORIES) - set(mapping))}, "
        f"yalnız frontend-də: {sorted(set(mapping) - set(CATEGORIES))}"
    )


def test_hər_ikon_svg_kitabxanasında_mövcuddur():
    """
    Xəritə mövcud olmayan ikona işarə etsə, `<use>` sükutla BOŞ çəkir -
    konsolda səhv yoxdur, sadəcə ikonun yeri boş qalır.
    """
    html = read_static("index.html")
    symbols = set(re.findall(r'<symbol id="icon-([\w-]+)"', html))
    for category, icon in parse_category_icons().items():
        assert icon in symbols, f"«{category}» üçün #icon-{icon} kitabxanada yoxdur"


# ------------------------------------------------------------ API müqaviləsi


def test_müqayisə_cavabı_kateqoriya_qaytarır():
    """
    Məhsul ikonu `category` sahəsindən seçilir. Sahə cavabdan çıxsa, bütün
    məhsullar eyni ikona düşərdi - səhifə isə yenə işləyərdi.
    """
    data = client.get("/api/basket/compare").json()
    for item in data["items"]:
        assert "category" in item, f"«{item['label']}» sətrində category yoxdur"
        assert item["category"] in CATEGORIES


def test_axtarış_cavabı_kateqoriya_qaytarır():
    """Axtarış nəticələrində də ikon göstərilir - eyni sahə lazımdır."""
    items = client.get("/api/products/search?q=").json()["items"]
    for item in items:
        assert "category" in item


def test_müqayisə_ən_ucuz_mümkün_cəmi_qaytarır():
    """
    Marketlərin assortimenti fərqli olanda heç biri səbətin hamısını satmır və
    `best` boş qalır. Həmin halda hero `cheapest` sahəsindən qidalanır —
    yəni istifadəçi yenə də bir rəqəm görür.

    Sahə itsə, hero ölü boz qutuya çevrilər: səhifə "işləyər", amma səhifənin
    əsas sualı cavabsız qalar.
    """
    data = client.get("/api/basket/compare").json()
    if not data["items"]:
        pytest.skip("səbət boşdur")

    cheapest = data["cheapest"]
    assert cheapest is not None
    assert cheapest["total"] > 0
    assert cheapest["store_count"] >= 1

    # Rəqəm UYDURULMUR: hər məhsulun ən ucuz qiymətinin cəmidir.
    expected = sum(
        item["prices"][str(item["cheapest_store_id"])]["price"] * item["qty"]
        for item in data["items"]
        if item["prices"]
    )
    assert cheapest["total"] == pytest.approx(round(expected, 2), abs=0.01)


def test_ən_ucuz_cəm_heç_bir_market_cəmindən_böyük_deyil():
    """
    Məntiq yoxlaması: hər məhsulu ƏN UCUZ satandan almaq, tək bir marketdən
    almaqdan bahalı ola bilməz.

    Bu, hesablamada işarə və ya çarpan səhvini tutur — belə səhv ekranda
    inandırıcı görünür, çünki rəqəm yenə də "normal" çıxır.
    """
    data = client.get("/api/basket/compare").json()
    if not data["items"] or not data["cheapest"]:
        pytest.skip("səbət boşdur")

    for store in data["stores"]:
        if store["complete"]:
            assert data["cheapest"]["total"] <= store["total"] + 0.01, (
                f"{store['store']} tək başına daha ucuzdur — hesablama səhvdir"
            )


# ------------------------------------------------ frontend selektorları canlı


def test_bütün_js_selektorları_html_də_mövcuddur():
    """
    Skriptlər yüklənəndə `getElementById(...).addEventListener(...)` çağırır.
    Element HTML-dən silinsə, həmin sətir `null`-a düşüb BÜTÜN faylı qırır -
    yəni bir ID-nin adı dəyişəndə səhifənin yarısı işləməyi dayandırır.
    """
    html = read_static("index.html")
    ids = set(re.findall(r'\bid="([^"]+)"', html))

    scripts = ["nav.js", "app.js", "advisor.js", "analytics.js", "scrape.js", "profile.js"]
    for name in scripts:
        source = read_static(name)
        wanted = set(re.findall(r'getElementById\("([^"]+)"\)', source))
        wanted |= set(re.findall(r'\$\("#([\w-]+)"\)', source))
        wanted |= set(re.findall(r'sel\("([\w-]+)"\)', source))
        wanted |= set(re.findall(r'advisorEl\("([\w-]+)"\)', source))
        missing = sorted(w for w in wanted if w not in ids)
        assert not missing, f"{name} olmayan elementi axtarır: {missing}"


# ------------------------------------------------------------ dizayn sistemi


def test_dark_mode_bloku_yoxdur():
    """Layihə həmişə işıq rejimindədir - sistem ayarı UI-ı dəyişməməlidir."""
    css = re.sub(r"/\*.*?\*/", "", read_static("style.css"), flags=re.S)
    assert "prefers-color-scheme: dark" not in css


def test_rənglər_yalnız_token_lərdən_gəlir():
    """
    `:root`-dan kənarda hardcoded rəng olmamalıdır.

    Səbəb praktikdir: brend rəngini dəyişmək bir sətir olmalıdır, 40 yer yox.
    İstisna: `rgba(0|16, …)` — kölgə və hairline üçün şəffaflıq, rəng deyil.
    """
    css = read_static("style.css")
    root = re.search(r":root\s*\{.*?\n\}", css, re.S).group(0)
    outside = css.replace(root, "")
    hits = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", outside)
    leaks = [h for h in hits if not re.match(r"rgba?\(\s*(0|16)\s*,", h)]
    assert not leaks, f"token-dən kənar rəng: {leaks}"


def test_semantik_rənglər_təyin_olunub():
    """
    Rəng MƏNA daşıyır, bəzək deyil. Hər token bir siqnaldır; biri dəyişsə,
    UI-da həmin məna itər.

    PALİTRA DƏYİŞDİ (trolley dizayn sistemi, istifadəçinin açıq qərarı).
    Əvvəl brend MAVİ idi, çünki yaşıl «qənaət» mənasını daşıyırdı. İndi brend
    trolley-in yaşılıdır, «ən ucuz» siqnalı isə rəngdən çıxarılıb ÇƏRÇİVƏYƏ
    verilib — bax `test_ən_ucuz_siqnalı_rənglə_verilmir`. Beləliklə bir yaşıl
    iki məna daşımır.

    Kəhrəba token-i YOXDUR: trolley palitrasında turuncu/kəhrəba yoxdur.
    «Təsdiqlənməyib» xəbərdarlıq deyil, məlumatdır — ona görə info mavisidir.
    """
    css = read_static("style.css")
    expected = {
        "--accent": "#00a300",   # brend, naviqasiya, əsas hərəkət
        "--ok": "#4caf50",       # təsdiqlənib / uğurlu
        "--info": "#0066b7",     # təsdiqlənməyib / yoxlaya bilmirik
        "--danger": "#cc3327",   # bahalı / şübhəli / xəta
        "--ai": "#8a005d",       # YALNIZ AI kartı
    }
    for token, value in expected.items():
        assert re.search(rf"{token}:\s*{value};", css, re.I), f"{token} != {value}"


def test_ən_ucuz_siqnalı_rənglə_verilmir():
    """
    Brend rəngi yaşıl olduğu üçün «ən ucuz» DOLU YAŞIL FON işlədə bilməz —
    əks halda eyni yaşıl həm brendi, həm ucuzluğu bildirərdi.

    Siqnal forma ilə verilir: çərçivə + ✓ nişanı. Kimsə fonu geri qaytarsa,
    bu test düşəcək.
    """
    css = read_static("style.css")
    block = re.search(r"\.price-pill\.is-best\s*\{(.*?)\}", css, re.S)
    assert block, ".price-pill.is-best qaydası tapılmadı"
    rule = block.group(1)
    assert "border:" in rule, "«ən ucuz» çərçivəsi yoxdur"
    assert "var(--accent)" in rule, "çərçivə brend rəngindən gəlməlidir"
    assert "background: var(--bg)" in rule, "fon neytral qalmalıdır"


def test_js_in_oxuduğu_hər_token_root_da_var():
    """
    REAL SƏHVDƏN ÇIXIB.

    `analytics.js` qrafik rənglərini CSS-dən oxuyur:
    `cssVar("--green", "#34C759")`. v2-də token adı `--ok` oldu, amma JS
    yenilənmədi — `getComputedStyle` boş sətir qaytardı və kod SƏSSİZCƏ
    ehtiyat hardcode rəngə düşdü. Qrafik yenə çəkilirdi, sadəcə səhifə ilə
    fərqli rəngdə: nə xəta, nə xəbərdarlıq.

    Bu test JS-in soruşduğu hər token-in `:root`-da mövcudluğunu yoxlayır.
    """
    css = read_static("style.css")
    root = re.search(r":root\s*\{.*?\n\}", css, re.S).group(0)
    declared = set(re.findall(r"(--[a-z0-9-]+)\s*:", root))

    for name in ["analytics.js", "app.js", "store-colors.js"]:
        source = read_static(name)
        wanted = set(re.findall(r'cssVar\(\s*"(--[a-z0-9-]+)"', source))
        wanted |= set(re.findall(r'getPropertyValue\(\s*"(--[a-z0-9-]+)"', source))
        missing = sorted(w for w in wanted if w not in declared)
        assert not missing, f"{name} olmayan token oxuyur: {missing}"


def test_səth_rəngləri_işıqlıdır():
    """Tünd fon heç vaxt yaranmamalıdır - layihə yalnız işıqlı rejimdədir."""
    css = read_static("style.css")
    assert re.search(r"--bg:\s*#ffffff;", css, re.I), "səhifə fonu dəyişib"
    assert re.search(r"--surface:\s*#f1f3f4;", css, re.I), "kart fonu dəyişib"


def test_market_palitrasında_status_rəngi_yoxdur():
    """
    Market rəng nöqtələri KİMLİK bildirir, status yox.

    Palitraya yaşıl və ya qırmızı düşsə, istifadəçi «bu market ucuzdur?» deyə
    düşünər — halbuki nöqtə sadəcə hansı market olduğunu göstərir. Bu, rəngin
    məna daşıması qaydasının ən asan pozulan yeridir.
    """
    css = read_static("style.css")
    palette = re.findall(r"--store-\d:\s*(#[0-9A-Fa-f]{6});", css)
    assert len(palette) == 6, f"6 market rəngi gözlənilirdi, {len(palette)} var"

    # Brend rəngi də bura daxildir: market nöqtəsi brendlə eyni yaşıl olsa,
    # «bu market seçilib?» sualı yaranar.
    status = {"#4CAF50", "#CC3327", "#00A300"}
    clash = status & {c.upper() for c in palette}
    assert not clash, f"market palitrasında status rəngi var: {clash}"


def test_verdict_səhifənin_ən_böyük_elementidir():
    """
    Səbətin ən ucuz cəmi (`.hero-price`) ölçüdə hər şeydən böyük olmalıdır.

    Bu, «verdict → qrafik → cədvəl → istisnalar» axınının vizual təməlidir:
    istifadəçi səhifəyə baxan kimi cavabı görməlidir. Kimsə stat rəqəmini
    böyüdüb bu iyerarxiyanı sükutla pozarsa, test düşəcək.
    """
    css = read_static("style.css")

    def size_of(selector: str) -> int:
        block = re.search(rf"\.{selector}\s*\{{[^}}]*?font-size:\s*(\d+)px", css, re.S)
        assert block, f".{selector} üçün font-size tapılmadı"
        return int(block.group(1))

    # `.hero-saving` siyahıdan ÇIXARILDI: v2-də hero yenidən quruldu və
    # «qənaət» bloku ümumiyyətlə yoxdur - qənaət indi cavabın altında bir
    # sətir (`.answer-alt`) kimi verilir, böyük rəqəm kimi yox.
    verdict = size_of("hero-price")
    for other in ["stat-value", "hero-store", "page-title", "chart-value"]:
        assert verdict > size_of(other), f".hero-price .{other}-dən böyük deyil"


def test_hər_hökmün_vizual_qarşılığı_var():
    """
    Backend-dəki VERDICTS ilə frontend-dəki VERDICT xəritəsi üst-üstə düşməlidir.

    Kateqoriya ikonları ilə eyni səssiz risk: backend yeni hökm qaytarsa,
    frontend onu xəritədə tapmayıb neytral boz pill verər — istifadəçi
    «şübhəli» ilə «təsdiqlənib» arasındakı fərqi görməz, amma heç bir yerdə
    xəta baş verməz.
    """
    from app.analytics import VERDICTS

    source = read_static("analytics.js")
    block = re.search(r"const VERDICT = \{(.*?)\n  \};", source, re.S)
    assert block, "VERDICT xəritəsi analytics.js-də tapılmadı"

    mapped = set(re.findall(r"^\s*(\w+):\s*\{", block.group(1), re.M))
    assert mapped == set(VERDICTS), (
        f"uyğunsuzluq — yalnız backend-də: {sorted(set(VERDICTS) - mapped)}, "
        f"yalnız frontend-də: {sorted(mapped - set(VERDICTS))}"
    )


def test_diqqət_tələb_edən_hökmlər_əvvəldədir():
    """
    Exception-first sıralama: «şübhəli» siyahının başında, «təsdiqlənib»
    sonunda olmalıdır.

    Sıra `rank` rəqəmi ilə verilir. Kimsə onu qarışdırsa, ən vacib sətirlər
    aşağı düşər və bölmənin bütün mənası itər — bu isə ekranda dərhal gözə
    dəymir, çünki siyahı yenə də "işləyir".
    """
    source = read_static("analytics.js")
    ranks = {
        name: int(rank)
        for name, rank in re.findall(r"(\w+):\s*\{\s*rank:\s*(\d+)", source)
    }
    assert ranks["subheli"] < ranks["tesdiqlenmeyib"] < ranks["tesdiqlenib"]


# ------------------------------------------------------------ brauzer keşi


def test_statik_fayllar_hər_dəfə_yenidən_yoxlanılır():
    """
    REAL SƏHVDƏN ÇIXIB: CSS/JS dəyişəndən sonra səhifə brauzerdə YENİLƏNMİRDİ.

    Səbəb `Cache-Control` başlığının ümumiyyətlə göndərilməməsi idi. Yalnız
    `etag` + `last-modified` olanda brauzer "evristik keşləmə" tətbiq edir -
    faylı serverdən SORUŞMADAN köhnə nüsxədən götürür. Nəticə: kod dəyişir,
    F5 basılır, heç nə olmur.

    `no-cache` "keşləmə" demək deyil - "hər dəfə soruş" deməkdir.
    """
    for path in ["/", "/static/style.css", "/static/app.js", "/static/index.html"]:
        header = client.get(path).headers.get("cache-control", "")
        assert "no-cache" in header, f"{path}: Cache-Control yoxdur ({header!r})"


def test_dəyişməyən_fayl_304_qaytarır():
    """
    `no-cache` sürəti İTİRMİR: fayl dəyişməyibsə server 304 verir və heç bir
    bayt ötürülmür. Bu test həmin balansı qoruyur - kimsə `no-store` yazsa
    (o, keşi tamamilə söndürür), test düşəcək.
    """
    first = client.get("/static/style.css")
    assert first.status_code == 200

    second = client.get("/static/style.css",
                        headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 304
    assert not second.content
