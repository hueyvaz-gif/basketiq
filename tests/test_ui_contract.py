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



def test_hər_kateqoriyanın_öz_ton_addımı_var():
    """
    M2.1: şəkli olmayan məhsul KATEQORİYA lövhəsi alır və lövhənin fonu
    ÜÇ NEYTRAL ton addımından biridir.

    QAYDA DƏYİŞDİ: əvvəl hər kateqoriyanın öz RƏNGİ vardı (süd mavi, ət
    çəhrayı). Şəbəkədə on kart yan-yana duranda ekran rəngli mozaikaya
    çevrilirdi - göz məhsula yox, fon rənglərinə düşürdü.

    Kateqoriya siyahısına yeni ad düşsə və ton unudulsa, səhv SƏSSİZ olardı:
    `--tile-tone` təyin olunmur, ehtiyat dəyər işə düşür və həmin kateqoriya
    həmişə eyni tonda qalır - fərq gözlə seçilmir.
    """
    css = read_static("style.css")
    for category, ikon in parse_category_icons().items():
        ton = "is-cat-other" if ikon == "package" else f"is-{ikon}"
        assert f".thumb.{ton}" in css, f"«{category}» üçün .thumb.{ton} qaydası yoxdur"

        blok = re.search(
            rf"\.thumb\.{re.escape(ton)}[^{{]*\{{[^}}]*--tile-tone:\s*var\((--tile[\w-]*)\)",
            css,
            re.S,
        )
        assert blok, f"«{category}» ton addımı təyin etmir"
        assert f"{blok.group(1)}:" in css, f"{blok.group(1)} :root-da yoxdur"


def test_lövhə_ikonları_monoxromdur():
    """
    M2.1: ikon rəngi ikinci dərəcəli MƏTN tonudur, kateqoriya rəngi deyil.
    Rəngli ikon geri qayıtsa, plitələr yenidən mozaikaya çevrilər.
    """
    css = read_static("style.css")
    blok = re.search(r"\.thumb\.is-cat svg \{([^}]*)\}", css, re.S)
    assert blok, ".thumb.is-cat svg qaydası tapılmadı"
    gövdə = blok.group(1)
    assert "var(--text-secondary)" in gövdə, "ikon monoxrom deyil"
    assert "--cat-" not in gövdə, "ikon hələ də kateqoriya rəngindən qidalanır"


def test_kateqoriya_ikonları_eyni_xətt_qalınlığındadır():
    """
    M2.1: «vahid stil» yalnız CSS ölçüsü deyil - SVG-nin özündə də xətt
    qalınlığı eyni olmalıdır. Bir ikon 2.2, digəri 1.7 olsaydı, eyni ölçüdə
    biri qalın, digəri nazik görünərdi və plitələr «yığılmamış» oxunardı.
    """
    sprite = read_static("icons.svg")
    qalınlıqlar = set()
    for ikon in set(parse_category_icons().values()):
        blok = re.search(rf'<symbol id="icon-{re.escape(ikon)}"(.*?)</symbol>', sprite, re.S)
        assert blok, f"#icon-{ikon} tapılmadı"
        qalınlıqlar |= set(re.findall(r'stroke-width="([0-9.]+)"', blok.group(1)))

    assert len(qalınlıqlar) == 1, f"kateqoriya ikonlarında müxtəlif xətt qalınlığı: {qalınlıqlar}"


def test_şəkilsiz_məhsul_ünvan_almır():
    """
    Lövhə qərarı UI-dadır, ona görə backend «şəkil yoxdur» halını AÇIQ
    bildirməlidir. Əvvəl burada placeholder ünvanı qaytarılırdı və UI
    «şəkil varmı?» sualına fayl adına baxaraq cavab verməli olardı.
    """
    from ingestion.images import image_url

    assert image_url(None) is None
    assert image_url("") is None
    assert image_url("araz-12.png") == "/static/images/products/araz-12.png"


def test_lövhə_ikonu_şəkil_ilə_birlikdə_yazılır():
    """
    Şəkil faylı diskdə olmaya bilər (`products/` qovluğu gitignore-dadır və
    `tools/build_images.py` ilə bərpa olunur). Ehtiyat qatı kateqoriyanı
    `data-cat` atributundan oxuyur - yəni atribut ŞƏKİLLİ halda da yazılmalıdır,
    əks halda fayl tapılmayanda lövhə boş qalar.
    """
    ui = read_static("ui.js")
    gövdə = re.search(r"function productThumb\(.*?\n\}", ui, re.S)
    assert gövdə, "productThumb tapılmadı"

    # Funksiyanın İKİ qolu var (şəkil / lövhə) və HƏR İKİSİ `data-cat` yazmalıdır.
    qollar = re.findall(r'<span class="\$\{[^"]*"([^>]*)>', gövdə.group(0))
    assert len(qollar) == 2, f"gözlənilən iki qol, tapıldı {len(qollar)}"
    for qol in qollar:
        assert "data-cat=" in qol, "lövhə qollarından biri data-cat yazmır"


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
        "app.js",
        "store-grid.js",
        "deals.js",
        "ads.js",
        "advisor.js",
        "analytics.js",
        "profile.js",
    ],
    # Admin səhifəsi AYRIDIR (P6): istifadəçi səhifəsi onun skriptlərini
    # ümumiyyətlə yükləmir.
    "admin.html": [
        "admin.js",
        "scrape.js",
        "review.js",
        "coverage.js",
        "ads-admin.js",
    ],
    "product.html": ["product.js"],
    "store.html": ["store.js"],
    "search.html": ["search.js"],
    "basket.html": ["basket-page.js"],
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
        # Paylaşılan köməkçilər DOM elementi axtarmır, ona görə siyahıda
        # yoxdurlar. `i18n.js` də bura düşür: o, HƏR səhifədə yüklənir və
        # yalnız `data-i18n` işarəsi olan elementlərə toxunur.
        # `basket-badge.js` də paylaşılandır: üst paneldəki rəqəm HƏR səhifədə
        # var və fayl öz elementini tapmasa sakitcə dayanır.
        shared = {"ui.js", "icons.js", "store-colors.js", "i18n.js", "basket-badge.js"}
        assert set(scripts) == linked - shared, (
            f"{page}: siyahı ilə HTML fərqlənir — "
            f"yalnız HTML-də: {sorted(linked - shared - set(scripts))}, "
            f"yalnız siyahıda: {sorted(set(scripts) - linked)}"
        )


# ------------------------------------------------------------ dizayn sistemi



def test_hər_açılan_bölmənin_dərəcəsi_var():
    """
    B10: açılan bölmələr iki dərəcəyə bölünür - `is-primary` (qiymət
    tarixçəsi) və `is-secondary` (AI qeydi, endirim yoxlaması, profil).

    Yeni bölmə dərəcəsiz əlavə olunsa, o, DEFOLT ölçüdə - yəni əsas bölmə
    kimi - görünər və iyerarxiya səssizcə pozular. Səhv gözlə görünməzdi:
    dörd bölmənin üçü kiçik, biri böyükdür, beşincisi də böyük çıxsa,
    «yəqin belə nəzərdə tutulub» deyilər.
    """
    html = read_static("index.html")
    foldlar = re.findall(r'<details class="([^"]*fold[^"]*)"', html)
    # `fold-inline` səhifə içindəki kiçik açılan sətirdir, kart deyil.
    kartlar = [c for c in foldlar if "fold-inline" not in c]
    assert kartlar, "açılan kart tapılmadı"

    for sinif in kartlar:
        assert "is-primary" in sinif or "is-secondary" in sinif, (
            f"dərəcəsiz açılan bölmə: class=\"{sinif}\""
        )

    css = read_static("style.css")
    assert ".fold.is-primary" in css and ".fold.is-secondary" in css


def test_sürüşən_cədvəl_qapsayıcısı_mövqedədir():
    """
    `.table-scroll` `position: relative` OLMALIDIR.

    BRAUZERDƏ TAPILDI (390px genişlik): səhifə 584px üfüqi sürüşürdü və
    sürüşən sahədə heç nə görünmürdü - ağ boşluq. Səbəb cədvəlin içindəki
    `position: absolute` olan `.sr-only` mətnləridir: qapsayıcının mövqeyi
    olmayanda onların qapsayan bloku səhifə özü olur, `overflow-x: auto`
    isə onları kəsmir.

    Bu test STATİKDİR, davranışı yoxlamır - amma düzəlişin SƏBƏBİNİ saxlayır.
    `position` sətri «lazımsız» görünüb silinsə, səhv geri qayıdar və yenə
    yalnız dar ekranda, özü də görünməyən boşluq kimi üzə çıxar.
    """
    css = read_static("style.css")
    blok = re.search(r"\.table-scroll \{([^}]*)\}", css)
    assert blok, ".table-scroll qaydası tapılmadı"
    assert "position: relative" in blok.group(1), (
        ".table-scroll mövqedə deyil - gizli mətn səhifəni üfüqi sürüşdürəcək"
    )


def test_kataloq_kəsikləri_istifadəçiyə_göstərilmir():
    """
    P5: kataloqdan kəsilmiş şəkil kartda GÖSTƏRİLMİR.

    Kəsiklərin nisbəti müxtəlifdir, kənarlarında qonşu kartın parçası qalır
    və fonları kataloqun öz rəngidir. Kartlar yan-yana düzüləndə nəticə
    səliqəsiz olur - biri ağ, biri sarı, biri yarımçıq. Emal zənciri saxlanılır
    (admin üçün faydalıdır), amma UI onları çəkmir.

    Səhv geri qayıtsa, gözlə dərhal seçilməz: bir neçə kartda şəkil, qalanında
    ikon olar və bu, «data belədir» kimi oxunar.
    """
    ui = read_static("ui.js")
    assert "CATALOG_CROP_PREFIX" in ui, "kəsik süzgəci yoxdur"
    assert "isCatalogCrop(item.image)" in ui, "şəkil qolu süzgəci işlətmir"


def test_bütün_məhsul_lövhələri_eyni_formadadır():
    """
    P5: eyni məhsul endirim siyahısında və axtarış kartında EYNİ formada
    görünməlidir. Əvvəl biri sabit piksel ölçüsü, digəri `aspect-ratio`
    işlədirdi və fonları da fərqli tokenlərdən gəlirdi.
    """
    css = read_static("style.css")
    for selektor in (".deal-photo", ".pcard-photo", ".product-photo"):
        blok = re.search(rf"\n{re.escape(selektor)} \{{(.*?)\}}", css, re.S)
        assert blok, f"{selektor} qaydası tapılmadı"
        gövdə = blok.group(1)
        assert "aspect-ratio: 1 / 1" in gövdə, f"{selektor} kvadrat deyil"
        assert "--bg-subtle" in gövdə, f"{selektor} ortaq fondan istifadə etmir"

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
        # «Ən ucuz» M2.3-də İSTİ AKSENTƏ keçdi: qənaət saytın vəd etdiyi
        # yeganə hərəkətdir, mavi ilə yazılanda isə hər digər interaktiv
        # elementlə eyni səviyyəyə düşürdü.
        "--cheapest": r"var\(--accent-hot\)",
        "--accent-hot": "#c2410c",   # LAYİHƏDƏ YEGANƏ isti rəng
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
    # BÜTÜN skriptlər yoxlanılır, təkcə `app.js` deyil.
    #
    # Əvvəl yalnız `app.js` oxunurdu və qayda yeni fayla KEÇMİRDİ: reklam
    # meneceri (`ads-admin.js`) öz silmə düyməsini təsdiqsiz yaza bilərdi və
    # test yenə yaşıl keçərdi.
    tapılan = 0
    for name in sorted(path.name for path in STATIC.glob("*.js")):
        lines = read_static(name).splitlines()
        silmələr = [i for i, line in enumerate(lines) if 'method: "DELETE"' in line]
        tapılan += len(silmələr)

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
                f"{name}:{i + 1} silmə təsdiqin arxasında deyil: {lines[i].strip()!r}"
            )

    assert tapılan >= 3, f"3 silmə sorğusu gözlənilirdi, {tapılan} tapıldı"


def test_təsdiq_ikinci_kliki_gözləyir():
    """
    `armDeleteButton()`-un özü: silmə YALNIZ eyni düymə artıq gözləyəndə
    çağırılmalıdır. Kimsə şərti götürsə, bir klik yenidən silərdi.
    """
    # Funksiya `ui.js`-dədir (P1-də köçürüldü): səbət səhifəsi də silmə
    # düyməsi çəkir və `app.js`-i o səhifəyə qoşmaq olmur.
    js = read_static("ui.js")
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


def test_silmə_düymələrinin_toxunma_sahəsi_44px_dir():
    """
    Apple HIG 44×44 tövsiyə edir — bu, TAPPABLE sahə haqqındadır, görüntünün
    özü haqqında yox. Ona görə görünən dairə kiçik qalır, `::before` isə onu
    44-ə tamamlayır. Dairəni böyütsək cədvəl sətirləri və üst panel ağırlaşardı.

    Ölçüldü (brauzerdə): `.icon-btn` görünən 36×36, toxunma 44×44;
    `.basket-chip-del` görünən 24×24, toxunma 44×44. Qonşu «Sətirlər» düyməsi
    ilə ara 16px-dir, örtük isə 4px uzanır — kəsişmə yoxdur.
    """
    css = read_static("style.css")
    for selektor, görünən in ((".icon-btn", 36), (".basket-chip-del", 24)):
        blok = re.search(rf"{re.escape(selektor)}::before \{{(.*?)\}}", css, re.S)
        assert blok, f"{selektor}::before qaydası tapılmadı — toxunma sahəsi genişlənmir"
        inset = re.search(r"inset:\s*-(\d+)px", blok.group(1))
        assert inset, f"{selektor}::before mənfi inset işlətmir"
        toxunma = görünən + 2 * int(inset.group(1))
        assert toxunma >= 44, f"{selektor} toxunma sahəsi {toxunma}px — 44 lazımdır"


def test_seçim_sətirləri_44px_hündürlükdədir():
    """
    Checkbox və radio üçün TOXUNMA HƏDƏFİ `<label>`-dir, qutunun özü deyil —
    etikete klik seçimi dəyişir.

    ÖLÇÜLDÜ: qutu 17×17 idi, etiket isə 139×32 — yəni WCAG 2.5.8 (24×24)
    onsuz da ödənilirdi, amma Apple-ın 44px sətir ölçüsündən aşağı idi.
    İndi hər iki etiket `min-height: 44px` alır.
    """
    css = read_static("style.css")
    for selektor in (".check", ".filter-opt"):
        blok = re.search(rf"{re.escape(selektor)} \{{(.*?)\}}", css, re.S)
        assert blok, f"{selektor} qaydası tapılmadı"
        hündür = re.search(r"min-height:\s*(\d+)px", blok.group(1))
        assert hündür, f"{selektor} üçün min-height yoxdur"
        assert int(hündür.group(1)) >= 44, (
            f"{selektor} sətri {hündür.group(1)}px — 44 lazımdır"
        )


def test_düymələrin_hündürlüyü_44px_dir():
    """
    Apple HIG-in 44px tappable ölçüsü indi düymələrin ÖZ hündürlüyüdür —
    görünməyən örtüyə ehtiyac qalmır.

    ÖLÇÜLDÜ (brauzerdə): `.btn` 44px, segmented yolu 44px (seqment 40 +
    2×2 daxili boşluq). Üst panel 93px-ə qalxdı — ekran şəkli ilə baxıldı,
    tarazlığı pozmur.
    """
    css = read_static("style.css")

    blok = re.search(r"\.btn \{(.*?)\}", css, re.S)
    assert blok, ".btn qaydası tapılmadı"
    hündür = re.search(r"min-height:\s*(\d+)px", blok.group(1))
    assert hündür and int(hündür.group(1)) >= 44, "düymə 44px-dən alçaqdır"

    # Segmented: seqmentin hündürlüyü + yolun daxili boşluğu 44-ə çatmalıdır.
    seg = re.search(r"\.seg-btn \{(.*?)\}", css, re.S)
    yol = re.search(r"\.segmented \{(.*?)\}", css, re.S)
    assert seg and yol, "segmented qaydaları tapılmadı"
    seg_h = int(re.search(r"min-height:\s*(\d+)px", seg.group(1)).group(1))
    yol_p = int(re.search(r"padding:\s*(\d+)px", yol.group(1)).group(1))
    assert seg_h + 2 * yol_p >= 44, f"segmented yolu {seg_h + 2 * yol_p}px — 44 lazımdır"


def test_forma_sahələri_düymə_ilə_eyni_hündürlükdədir():
    """
    `input` və `select` düymə ilə YAN-YANA dayanır (admin yükləmə forması).
    Əvvəl 41-43px idi, düymə isə 44 — 3px fərq sətri əyri göstərirdi.

    Hündürlük `padding` ilə yox, `min-height` ilə verilir: padding şrift
    ölçüsündən asılıdır və şrift dəyişəndə sahə sürüşür.
    """
    css = read_static("style.css")
    blok = re.search(r"\.field input, \.field select \{(.*?)\}", css, re.S)
    assert blok, ".field input/select qaydası tapılmadı"
    hündür = re.search(r"min-height:\s*(\d+)px", blok.group(1))
    assert hündür, "forma sahəsi üçün min-height yoxdur"
    assert int(hündür.group(1)) >= 44, f"forma sahəsi {hündür.group(1)}px — 44 lazımdır"


# ------------------------------------------------------- üç dil (AZ / EN / RU)


def i18n_keys() -> dict[str, set[str]]:
    """`i18n.js`-dəki hər açar üçün hansı dillərin yazıldığını qaytarır."""
    js = read_static("i18n.js")
    başlanğıc = js.index("const DICT = {")
    son = js.index("\n  };", başlanğıc)
    blok = js[başlanğıc:son]

    açarlar: dict[str, set[str]] = {}
    for m in re.finditer(r'"([\w.\- əçğıöşüƏÇĞİÖŞÜ]+)":\s*\{(.*?)\},?\n', blok, re.S):
        açar, gövdə = m.group(1), m.group(2)
        açarlar[açar] = set(re.findall(r"\b(az|en|ru):", gövdə))
    return açarlar


def test_hər_açar_üç_dildə_var():
    """
    Bir dili unutmaq ən asan səhvdir və EKRANDA GÖRÜNMÜR: `t()` tapmadığı
    dildə azərbaycancaya düşür, yəni rus interfeysində birdən azərbaycanca
    söz peyda olur — nə xəta, nə xəbərdarlıq.
    """
    açarlar = i18n_keys()
    assert len(açarlar) > 150, f"lüğət çox kiçikdir: {len(açarlar)} açar"

    natamam = {a: sorted({"az", "en", "ru"} - d) for a, d in açarlar.items() if len(d) != 3}
    assert not natamam, f"dil əskikdir: {natamam}"


def test_html_də_işarələnən_hər_açar_lüğətdə_var():
    """
    `data-i18n="yoxdur.acar"` yazsan, ekranda açarın ÖZÜ görünər.
    Bu, tərcümədə ən çox rast gəlinən yazı səhvidir.
    """
    açarlar = set(i18n_keys())
    for page in all_pages():
        html = read_static(page)
        istifadə = set(re.findall(r'data-i18n="([^"]+)"', html))
        for cüt in re.findall(r'data-i18n-attr="([^"]+)"', html):
            istifadə |= {p.split(":")[1].strip() for p in cüt.split(";") if ":" in p}
        çatışmayan = sorted(istifadə - açarlar)
        assert not çatışmayan, f"{page} lüğətdə olmayan açar işlədir: {çatışmayan}"


def test_js_də_çağırılan_hər_açar_lüğətdə_var():
    """Eyni səhv JS tərəfində də mümkündür: `t("yanlış.acar")`."""
    açarlar = set(i18n_keys())
    scripts = sorted({name for names in SCRIPT_PAGES.values() for name in names})
    for name in scripts:
        js = read_static(name)
        # Yalnız SABİT açarlar yoxlanılır; `t("cat." + c.name)` kimi
        # hesablanan açarlar ehtiyat mətnlə çağırılır və onlar buraya düşmür.
        # `(?<![\w.])` vacibdir: onsuz `params.get("q")` da `t(` kimi oxunur
        # və test uydurma açar tapır.
        istifadə = set(re.findall(r'(?<![\w.])t\("([\w.]+)"\s*[,)]', js))
        çatışmayan = sorted(istifadə - açarlar)
        assert not çatışmayan, f"{name} lüğətdə olmayan açar çağırır: {çatışmayan}"


def test_dil_keçidi_hər_səhifədədir():
    """Dil seçimi bir səhifədə itsə, istifadəçi ora düşəndə ilişib qalır."""
    for page in all_pages():
        html = read_static(page)
        assert 'class="lang-switch"' in html, f"{page} dil keçidi yoxdur"
        for lang in ("az", "en", "ru"):
            assert f'data-lang="{lang}"' in html, f"{page} {lang} düyməsi yoxdur"


def test_backendin_göndərdiyi_hər_açar_lüğətdə_var():
    """
    Backend cümlələri AÇAR + PARAMETR şəklində gəlir (`reason_keys`,
    `summary_keys`). Açar lüğətdə yoxdursa, ekranda AÇARIN ÖZÜ görünər —
    «reason.tooDeep» kimi. Bu, ən çirkin, ən asan buraxılan səhvdir.

    Açarlar Python mənbəyindən oxunur, cavabdan yox: endirim səbəbləri yalnız
    müəyyən datada yaranır, yəni canlı cavab hamısını göstərməyə bilər.
    """
    açarlar = set(i18n_keys())
    kök = Path(__file__).resolve().parent.parent / "app"

    backend_açarları = set()
    for path in (kök / "analytics.py", kök / "profile.py"):
        backend_açarları |= set(re.findall(r'"key":\s*"([\w.]+)"', path.read_text(encoding="utf-8")))

    assert backend_açarları, "backend heç bir açar göndərmir — bağlantı qırılıb"
    çatışmayan = sorted(backend_açarları - açarlar)
    assert not çatışmayan, f"backend lüğətdə olmayan açar göndərir: {çatışmayan}"


def test_backend_azərbaycanca_mətni_də_göndərir():
    """
    Açar sistemi mətni ƏVƏZ ETMİR, onun yanına gəlir.

    Səbəb: modelin promptu azərbaycancadır və MCP/n8n klientləri həmin mətni
    oxuyur. Kimsə mətni silib yalnız açar qoysa, AI zənciri və avtomatlaşdırma
    səssizcə boş sətir alardı.
    """
    from app.profile import Profile

    profil = Profile(household_size=2, weekly_budget=100, max_stores=2)
    assert "nəfərlik ev" in profil.summary(), "azərbaycanca xülasə itib"
    açarlar = [p["key"] for p in profil.summary_keys()]
    assert "sum.household" in açarlar
    assert len(açarlar) >= 3


# ============================================================================
# MARKET LOQOLARI (C13)
# ============================================================================

LOQO_SINIFLƏRI = (".store-logo-box", ".pricecol-logo", ".wtb-logo")


def test_loqo_qutuları_tək_nisbətdən_qidalanır():
    """
    Loqo dörd yerdə görünür: market şəbəkəsi, market səhifəsinin başlığı,
    endirim kartının qiymət sütunu, «harada almalı» cədvəli. Əvvəl dördünün
    də nisbəti fərqli idi (3.5:1, 1.3:1, 3.4:1, 3.8:1) və eyni loqo bir
    yerdə enli, başqa yerdə kvadrat görünürdü.

    Qayda: ölçü YALNIZ hündürlükdən gəlir, eni `--logo-ratio` hesablayır.
    Hər hansı qaydaya bərk `width` qayıtsa, nisbət yenidən ayrılar.
    """
    css = read_static("style.css")
    assert "--logo-ratio:" in css, "loqo nisbəti tokeni yoxdur"

    for sinif in LOQO_SINIFLƏRI:
        blok = re.search(rf"\n{re.escape(sinif)}\s*\{{(.*?)\}}", css, re.S)
        assert blok, f"{sinif} qaydası tapılmadı"
        gövdə = blok.group(1)
        assert "aspect-ratio: var(--logo-ratio)" in gövdə, f"{sinif} ümumi nisbəti işlətmir"
        # `(?<![-\w])` olmasa `max-width: 100%` da «bərk en» kimi oxunur —
        # halbuki o, əksinə, qutunun dar ekranda kiçilməsini təmin edir.
        assert not re.search(r"(?<![-\w])width:\s*\d", gövdə), (
            f"{sinif} bərk en yazır — nisbət qırılır"
        )


def test_loqo_faylları_eyni_nisbətdədir():
    """
    CSS qutunu bərabərləşdirir, faylların özü isə bərabər olmasa fayda yoxdur:
    `object-fit: contain` boşluğu da şəkil sayır. Əvvəl `rahat.png`-in ~78%-i
    boş ağ sahə idi və eyni qutuda o, `bazar.png`-dən iki dəfə kiçik görünürdü.

    `tools/normalize_logos.py` hamısını 4:1 kətana, BƏRABƏR MÜRƏKKƏB SAHƏSİ
    ilə yerləşdirir. Yeni market əlavə edən həmin aləti işlətməlidir.
    """
    from PIL import Image

    qovluq = Path(__file__).resolve().parent.parent / "app" / "static" / "images"
    fayllar = sorted(qovluq.glob("*.png"))
    assert len(fayllar) >= 4, "market loqoları tapılmadı"

    for f in fayllar:
        en, hünd = Image.open(f).size
        assert abs(en / hünd - 4.0) < 0.02, f"{f.name} nisbəti 4:1 deyil ({en}x{hünd})"


# ============================================================================
# M3: ŞƏKİLLİ VƏ İKONLU KART YAN-YANA
# ============================================================================


def test_şəkilli_plitənin_fonu_tokendəndir():
    """
    M3: şəkilli plitənin fonu kartın öz səthidir, kateqoriya tonu DEYİL.

    BRAUZERDƏ ÖLÇÜLDÜ: mənbə fotolarının fonu ağdır, ona görə tonlu plitənin
    ortasında ağ düzbucaqlı görünürdü - «qutu içində qutu». Qayda tokendən
    qidalanmalıdır ki, səth rəngi bir yerdən idarə olunsun.
    """
    css = read_static("style.css")
    blok = re.search(r"\.thumb\.is-photo \{([^}]*)\}", css, re.S)
    assert blok, ".thumb.is-photo qaydası tapılmadı"
    assert "var(--surface-card)" in blok.group(1), "şəkilli plitə tokendən qidalanmır"

    # Şəkilli qol yenə də kateqoriyanı yazır: fayl açılmasa ehtiyat qatı
    # ikonu məhz oradan tapır.
    ui = read_static("ui.js")
    gövdə = re.search(r"function productThumb\(.*?\n\}", ui, re.S)
    assert gövdə, "productThumb tapılmadı"
    assert "categoryTone(" in gövdə.group(0).split("return")[1]


def test_şəkil_sıçrayışın_qarşısını_alan_atributlarla_yazılır():
    """
    `loading="lazy"` trafik üçün, `width`/`height` isə LAYOUT üçündür:
    ölçüsüz şəkil gələndə kart hündürlüyü dəyişir və altındakı bütün
    şəbəkə tullanır.
    """
    ui = read_static("ui.js")
    gövdə = re.search(r"function productThumb\(.*?\n\}", ui, re.S)
    assert 'loading="lazy"' in gövdə.group(0)
    assert "image_w" in gövdə.group(0) and "image_h" in gövdə.group(0)


def test_şəkil_yüklənməsə_ikona_qayıdır():
    """
    Fayl silinsə və ya 404 versə, istifadəçi qırıq şəkil nişanı GÖRMƏMƏLİDİR.
    Ehtiyat qatı `is-photo`-nu da götürməlidir: fotoya aid içəri boşluq
    ikonun ölçüsünü kiçildərdi.
    """
    ui = read_static("ui.js")
    assert 'classList.remove("is-photo")' in ui
    assert 'classList.add("is-cat"' in ui


def test_iki_şəkil_prefiksi_qarışdırılmır():
    """
    İki ünvan prefiksi bir-birinə çox bənzəyir və mənaları TƏRSDİR:

        /static/images/products/   kataloq kəsiyi -> GÖSTƏRİLMİR
        /static/product_images/    real foto      -> GÖSTƏRİLİR

    Sözlərin yeri dəyişsə, ya bütün fotolar səssizcə itər, ya da bütün
    kəsiklər ekrana çıxar. İkisi də səssiz sınmadır - test dəyərləri
    kilidləyir.
    """
    from app.services.product_images import IMAGE_URL_PREFIX
    from ingestion.images import image_url

    assert IMAGE_URL_PREFIX == "/static/product_images"
    assert image_url("araz-12.png") == "/static/images/products/araz-12.png"

    ui = read_static("ui.js")
    assert 'CATALOG_CROP_PREFIX = "/static/images/products/"' in ui
    # Süzgəc real fotonu ATMAMALIDIR: prefikslərdən biri digərinin əvvəli
    # olsaydı, `startsWith` real fotonu da kəsik sayardı.
    assert not IMAGE_URL_PREFIX.startswith("/static/images/products/")


def test_market_kartında_məhsul_sayı_göstərilmir():
    """
    Kartın işi marketi TANITMAQDIR - loqo və ad bunu edir.

    Say isə müqayisə üçün mənasız rəqəmdir: «13 139» ilə «379» arasındakı
    fərq marketin zənginliyini yox, data mənbəyimizin növünü göstərir
    (Bravo mağaza qatından, Araz həftəlik kataloqdan gəlir). İstifadəçi
    bunu bilmir və rəqəmi market haqqında hökm kimi oxuyur.
    """
    js = read_static("store-grid.js")
    assert "market.products" not in js, "kartda məhsul sayı yenidən göstərilir"
    assert "stores.productCount" not in js


def test_tezliklə_yazısı_qalır():
    """
    «Tezliklə» say DEYİL - datası olmayan marketin vəziyyətini bildirir.
    Onsuz kart boş görünər və «niyə bu marketin qiyməti yoxdur?» sualı
    cavabsız qalardı (D15).
    """
    js = read_static("store-grid.js")
    assert 'common.soon' in js
    assert "is-soon-text" in js
