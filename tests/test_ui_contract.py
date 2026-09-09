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
    """
    `ui.js`-dəki CATEGORY_ICON xəritəsini oxuyur.

    XƏRİTƏ ARTIQ `app.js`-DƏ DEYİL: məhsul səhifəsi (`product.js`) də eyni
    ikonları çəkir, `app.js`-i isə oraya qoşmaq olmur (o, yükləndiyi anda
    yalnız ana səhifədə mövcud olan elementləri axtarır). Paylaşılan hissə
    `ui.js`-ə ayrıldı — məhz ona görə ki, xəritənin İKİ nüsxəsi olmasın.
    """
    source = read_static("ui.js")
    block = re.search(r"const CATEGORY_ICON = \{(.*?)\n\};", source, re.S)
    assert block, "CATEGORY_ICON xəritəsi ui.js-də tapılmadı"
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


def sprite_symbols() -> set[str]:
    """İkon kitabxanasındakı bütün `#icon-*` adları."""
    return set(re.findall(r'<symbol id="icon-([\w-]+)"', read_static("icons.svg")))


def test_hər_ikon_svg_kitabxanasında_mövcuddur():
    """
    Xəritə mövcud olmayan ikona işarə etsə, `<use>` sükutla BOŞ çəkir -
    konsolda səhv yoxdur, sadəcə ikonun yeri boş qalır.
    """
    symbols = sprite_symbols()
    for category, icon in parse_category_icons().items():
        assert icon in symbols, f"«{category}» üçün #icon-{icon} kitabxanada yoxdur"


def test_səhifələrin_istinad_etdiyi_hər_ikon_mövcuddur():
    """
    HTML və JS-dəki HƏR `#icon-...` istinadı kitabxanada olmalıdır.

    Əvvəl yalnız kateqoriya ikonları yoxlanılırdı. İndi iki səhifə var və
    ikonlar ayrıca faylda saxlanılır — səhv ad yazmaq (`#icon-shied`) daha
    asandır, nəticəsi isə eynilə səssizdir: ikonun yeri boş qalır, konsolda
    xəta yoxdur.
    """
    symbols = sprite_symbols()
    # Fayllar SİYAHIDAN yox, qovluqdan gəlir: yeni səhifə və ya skript
    # yarananda o, avtomatik olaraq yoxlamaya düşür.
    pages_and_scripts = all_pages() + sorted(
        path.name for path in STATIC.glob("*.js")
    )
    for name in pages_and_scripts:
        used = set(re.findall(r'#icon-([\w-]+)', read_static(name)))
        missing = sorted(u for u in used if u not in symbols)
        assert not missing, f"{name} olmayan ikona istinad edir: {missing}"


def test_ikon_kitabxanasının_ikinci_nüsxəsi_yoxdur():
    """
    Sprite YALNIZ `icons.svg`-də olmalıdır.

    Kimsə onu yenidən HTML-in içinə köçürsə, iki nüsxə yaranar: biri
    yenilənib digəri köhnə qalar və səhifə yenə «işləyər» — sadəcə səhv
    ikon göstərər. Belə fərqi gözlə tapmaq praktiki olaraq mümkün deyil.
    """
    for page in all_pages():
        assert '<symbol id="icon-' not in read_static(page), (
            f"{page} ikon sprite-ının ikinci nüsxəsini saxlayır — "
            "kitabxana yalnız icons.svg-də olmalıdır"
        )


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


# Hansı skript hansı səhifədə işləyir.
#
# ARTIQ İKİ SƏHİFƏ VAR. Əvvəl siyahı sadə idi, çünki hər şey `index.html`-də
# idi. İndi `product.js` yalnız `product.html`-də yüklənir - onu ana səhifənin
# ID-ləri ilə tutuşdursaq, test yalan yerə düşərdi.
SCRIPT_PAGES = {
    "index.html": [
        "nav.js",
        "app.js",
        "store-grid.js",
        "deals.js",
        "advisor.js",
        "analytics.js",
        "scrape.js",
        "profile.js",
    ],
    "product.html": ["product.js"],
    "store.html": ["store.js"],
    "search.html": ["search.js"],
}


def all_pages() -> list[str]:
    """`app/static/` içindəki BÜTÜN HTML səhifələri."""
    return sorted(path.name for path in STATIC.glob("*.html"))


def test_hər_səhifə_müqavilədə_qeydiyyatdadır():
    """
    Yeni səhifə əlavə olunanda o, avtomatik olaraq YOXLANMALIDIR.

    REAL SƏHVDƏN ÇIXIB: `search.html` yaradıldı, `SCRIPT_PAGES` isə əl ilə
    yazıldığı üçün yenilənmədi. Nəticədə bütün müqavilə testləri yaşıl
    keçirdi, halbuki yeni səhifənin nə ID-ləri, nə ikonları, nə də skript
    sırası bir dəfə də yoxlanmamışdı. Siyahını fayl sistemi ilə tutuşdurmaq
    bu boşluğu bağlayır.
    """
    missing = [page for page in all_pages() if page not in SCRIPT_PAGES]
    assert not missing, (
        f"bu səhifələr SCRIPT_PAGES-də yoxdur və heç bir testə düşmür: {missing}"
    )


def test_bütün_js_selektorları_html_də_mövcuddur():
    """
    Skriptlər yüklənəndə `getElementById(...).addEventListener(...)` çağırır.
    Element HTML-dən silinsə, həmin sətir `null`-a düşüb BÜTÜN faylı qırır -
    yəni bir ID-nin adı dəyişəndə səhifənin yarısı işləməyi dayandırır.
    """
    for page, scripts in SCRIPT_PAGES.items():
        ids = set(re.findall(r'\bid="([^"]+)"', read_static(page)))
        for name in scripts:
            source = read_static(name)
            wanted = set(re.findall(r'getElementById\("([^"]+)"\)', source))
            wanted |= set(re.findall(r'\$\("#([\w-]+)"\)', source))
            wanted |= set(re.findall(r'sel\("([\w-]+)"\)', source))
            wanted |= set(re.findall(r'advisorEl\("([\w-]+)"\)', source))
            wanted |= set(re.findall(r'\bel\("([\w-]+)"\)', source))

            # SKRİPTİN ÖZÜ YARATDIĞI elementlər də mövcud sayılır.
            #
            # `search.js` filtr menyusunu `innerHTML` ilə çəkir və sonra öz
            # yaratdığı `#categoryFilter`-i axtarır. HTML-də belə ID yoxdur,
            # amma səhv də yoxdur - element sorğu anında mövcuddur. Bu
            # istisna olmasa, dinamik səhifə yazmaq mümkün olmazdı.
            created = set(re.findall(r'id="([\w-]+)"', source))
            missing = sorted(w for w in wanted if w not in ids and w not in created)
            assert not missing, f"{name} ({page}) olmayan elementi axtarır: {missing}"


def test_hər_skript_bir_səhifədə_qoşulub():
    """
    `SCRIPT_PAGES` reallıqla üst-üstə düşməlidir.

    Yuxarıdakı test yalnız SİYAHIDAKI faylları yoxlayır. Kimsə yeni skript
    yazıb HTML-ə qoşsa, amma siyahıya yazmasa, o fayl bir daha heç vaxt
    yoxlanmazdı — yəni müqavilə sükutla deşilərdi.
    """
    for page, scripts in SCRIPT_PAGES.items():
        html = read_static(page)
        linked = set(re.findall(r'<script src="/static/([\w.-]+)"', html))
        # Paylaşılan köməkçilər (`ui.js`, `icons.js`, `store-colors.js`) DOM
        # elementi axtarmır, ona görə siyahıda yoxdurlar.
        shared = {"ui.js", "icons.js", "store-colors.js"}
        assert set(scripts) == linked - shared, (
            f"{page}: siyahı ilə HTML fərqlənir — "
            f"yalnız HTML-də: {sorted(linked - shared - set(scripts))}, "
            f"yalnız siyahıda: {sorted(set(scripts) - linked)}"
        )


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

    PALİTRA APPLE DİLİNƏ KEÇDİ (istifadəçinin açıq qərarı, 2026-09-09).
    YAŞIL TAM ÇIXARILDI — loqo, düymələr, nişanlar, «ən ucuz» siqnalı.
    Yeganə vurğu Apple mavisidir.

    Hər dəyərin ağ fonda kontrastı ölçülüb və AA-dan keçir:
      #0071e3 4.70:1 · #0066cc 5.57:1 · #6e6e73 5.07:1 · #d70015 5.38:1 ·
      #8944ab 6.04:1. Apple-ın öz #ff3b30 qırmızısı cəmi 3.55:1 verdiyi üçün
      onun tünd variantı götürülüb.

    --info BOZDUR və bu, qəsdəndir: «yoxlaya bilmirik» məlumatın YOXLUĞUDUR,
    onu rənglə vurğulamaq yanlış siqnal olardı.
    """
    css = read_static("style.css")
    expected = {
        "--accent": "#0071e3",     # brend, naviqasiya, əsas hərəkət
        "--accent-hover": "#0077ed",
        "--link": "#0066cc",       # mətn içindəki keçid
        "--cheapest": "#0071e3",   # ƏN UCUZ — öz token-i
        "--ok": "#0066cc",         # təsdiqlənib
        "--info": "#6e6e73",       # yoxlaya bilmirik — neytral
        "--danger": "#d70015",     # bahalı / şübhəli / xəta
        "--ai": "#8944ab",         # YALNIZ AI kartı
    }
    for token, value in expected.items():
        assert re.search(rf"{token}:\s*{value};", css, re.I), f"{token} != {value}"


def test_ən_ucuz_siqnalı_yalnız_rənglə_verilmir():
    """
    «Ən ucuz» rəngi brendin rəngi ilə EYNİDİR (hər ikisi Apple mavisi), ona
    görə dolu mavi fon işlədilə bilməz — «ucuz» ilə «seçilmiş» eyni görünərdi.

    Siqnal forma ilə gücləndirilir: çərçivə + ✓ nişanı, fon neytral.
    Kimsə dolu fon qaytarsa, bu test düşəcək.
    """
    css = read_static("style.css")
    block = re.search(r"\.price-pill\.is-best\s*\{(.*?)\}", css, re.S)
    assert block, ".price-pill.is-best qaydası tapılmadı"
    rule = block.group(1)
    assert "border:" in rule, "«ən ucuz» çərçivəsi yoxdur"
    assert "var(--cheapest)" in rule, "çərçivə «ən ucuz» token-indən gəlməlidir"
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
    assert re.search(r"--bg-subtle:\s*#f5f5f7;", css, re.I), "bölmə fonu dəyişib"


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
    status = {"#0071E3", "#0066CC", "#D70015", "#8944AB", "#6E6E73"}
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


# ------------------------------------------------ silmə təsdiqi (real risk)


def test_hər_silmə_sorğusu_təsdiqin_arxasındadır():
    """
    Silmə düymələri TƏSDİQSİZ idi: bir klik kataloqu (və onun bütün
    qiymətlərini) və ya səbət sətrini dərhal silirdi. Canlı yoxlamada göründü
    (`logs/notes.md`, 2026-09-09).

    İndi hər silmə `armDeleteButton()`-un içindədir — o, ikinci kliki gözləyir.
    Test hər `DELETE` sorğusundan GERİYƏ gedib ilk qeydiyyat nöqtəsini tapır:
    o, `armDeleteButton(` olmalıdır, birbaşa `addEventListener("click"` yox.

    Bu test STATİKDİR — kodun formasını yoxlayır, davranışı yox. Davranış
    brauzerdə ayrıca yoxlanılıb (bax `logs/notes.md`).
    """
    lines = read_static("app.js").splitlines()
    silmələr = [i for i, line in enumerate(lines) if 'method: "DELETE"' in line]
    assert len(silmələr) >= 3, f"3 silmə sorğusu gözlənilirdi, {len(silmələr)} tapıldı"

    for i in silmələr:
        qeydiyyat = None
        for j in range(i, -1, -1):
            if "armDeleteButton(" in lines[j]:
                qeydiyyat = "armDeleteButton"
                break
            if 'addEventListener("click"' in lines[j]:
                qeydiyyat = "addEventListener"
                break
        assert qeydiyyat == "armDeleteButton", (
            f"{i + 1}-ci sətirdəki silmə təsdiqin arxasında deyil: {lines[i].strip()!r}"
        )


def test_təsdiq_ikinci_kliki_gözləyir():
    """
    `armDeleteButton()`-un özü: silmə YALNIZ eyni düymə artıq gözləyəndə
    çağırılmalıdır. Kimsə şərti götürsə, bir klik yenidən silərdi.
    """
    js = read_static("app.js")
    yer = js.find("pendingDelete.btn === btn")
    assert yer > 0, "təsdiq şərti tapılmadı — iki addımlı silmə pozulub"

    # Şərtdən sonrakı blok silməni çağırmalıdır.
    assert "await onConfirm()" in js[yer : yer + 400], (
        "silmə əməliyyatı təsdiq şərtinin içində deyil"
    )
    assert "Escape" in js, "Escape ilə ləğv yoxdur"
    assert "DELETE_CONFIRM_MS" in js, "avtomatik ləğv taymeri yoxdur"


def test_silmə_təsdiqi_native_confirm_işlətmir():
    """
    `confirm()` səhifəni BLOKLAYIR — brauzer avtomatlaşdırması (bizim öz
    Selenium yoxlamalarımız da daxil) dialoq açılan kimi cavab verməyi
    dayandırır. Üstəlik onu üslublandırmaq mümkün deyil və düymələri
    ingiliscə gəlir, halbuki interfeys tam azərbaycancadır.
    """
    scripts = sorted({name for names in SCRIPT_PAGES.values() for name in names})
    assert scripts, "skript siyahısı boşdur"
    for name in scripts:
        # Şərhlər çıxarılır: `app.js`-də məhz BU QƏRARIN izahı var və orada
        # `confirm()` sözü keçir. Şərhi saymasaq, test öz sənədini cəzalandırardı.
        kod = re.sub(r"/\*.*?\*/", "", read_static(name), flags=re.S)
        kod = re.sub(r"^\s*//.*$", "", kod, flags=re.M)
        assert not re.search(r"(?<![.\w])confirm\s*\(", kod), (
            f"{name} native confirm() işlədir"
        )


def test_toxunma_hədəfləri_24px_dən_kiçik_deyil():
    """
    WCAG 2.5.8 (AA) toxunma hədəfi üçün MİNİMUM 24×24 px tələb edir.

    REAL ÖLÇMƏDƏN ÇIXIB: səbət çipindəki «sil» düyməsi 20×20 idi — mobil
    emulyasiyada barmaq ölçüsündə hədəf üçün çox kiçik. İndi 24×24-dür,
    üstəlik `::before` ilə görünməyən 44×44 sahə var (Apple HIG).
    """
    css = read_static("style.css")
    blok = re.search(r"\.basket-chip-del \{(.*?)\}", css, re.S)
    assert blok, ".basket-chip-del qaydası tapılmadı"

    ölçü = re.search(r"width:\s*(\d+)px;\s*height:\s*(\d+)px", blok.group(1))
    assert ölçü, "düymənin ölçüsü tapılmadı"
    en, hündür = int(ölçü.group(1)), int(ölçü.group(2))
    assert en >= 24 and hündür >= 24, f"toxunma hədəfi çox kiçikdir: {en}×{hündür}"
