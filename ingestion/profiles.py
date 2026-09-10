"""
MARKET BAŞINA EMAL PROFİLİ (D14) — «adapter» qatı.

PROBLEM: Araz üçün emal zənciri işləyir, qalan üç market üçün isə hər dəfə
sıfırdan qərar vermək lazım gəlirdi - kataloq hansı formatdadır, OCR hansı
rejimdə oxumalıdır, neçə səhifədir, səhifə JS ilə çəkilirmi. Bu qərarlar
kodun içində, iki ayrı yerdə (avtomatik çəkiliş və əl ilə yükləmə) səpələnmişdi.

BU FAYL HƏMİN QƏRARLARIN YEGANƏ YERİDİR. Yeni market əlavə etmək = bura bir
sətir yazmaq; hər iki axın (scrape və upload) onu avtomatik oxuyur.

VƏZİYYƏT SAHƏSİ QƏSDƏN VAR. Üç marketin mənbəyi hazırda ÖLÇÜLMÜŞ səbəblərlə
işləmir (`logs/sources.md`). Onları siyahıdan silmək iki dəfə zərərlidir:
kod hazır olduğu halda «dəstəklənmir» görünər, və səbəb yaddan çıxar. Ona görə
market qalır, vəziyyəti isə açıq yazılır - admin panelində elə o görünür.

VACİB: BU FAYL DATA GƏTİRMİR. Profil yalnız «necə oxumalı» sualına cavabdır.
Mağazanın qiymətləri kataloq yüklənəndə və ya mənbədən çəkiləndə yaranır -
bu, data işidir, kod işi deyil.
"""

from __future__ import annotations

from dataclasses import dataclass

# Vəziyyətlər
ACTIVE = "active"        # mənbə işləyir, çəkiliş mümkündür
MANUAL = "manual"        # avtomatik mənbə yoxdur; kataloq əl ilə yüklənir
BLOCKED = "blocked"      # mənbə var, amma ölçülmüş səbəbdən əlçatmazdır


@dataclass(frozen=True)
class StoreProfile:
    """
    Bir marketin kataloqunun NECƏ oxunduğu.

    `slug` `app/stores.py`-dakı reyestrlə eyni olmalıdır - `test_profiles.py`
    bunu yoxlayır, əks halda profil heç vaxt tapılmazdı və səssizcə defolta
    düşərdi.
    """

    slug: str
    fmt: str                      # "pdf" | "image" | "html"
    status: str
    note: str
    page_url: str | None = None   # avtomatik çəkiliş üçün kataloq səhifəsi

    # MAĞAZA (SAYT) QATI — kataloqdan AYRI mənbə (`ingestion/shop.py`).
    # `page_url` həftəlik endirim jurnalını, `shop_url` isə onlayn mağazanın
    # gündəlik rəf qiymətini verir. Bir market yalnız birinə sahib ola bilər:
    # Arazda kataloq var, mağaza yoxdur (robots `/api/`-ni bağlayır);
    # Bravoda əksinə.
    shop_url: str | None = None

    # --- OCR / parse profili ---
    # `None` = `.env`-dəki ümumi defolt işlədilir. Marketə xas dəyər YALNIZ
    # ölçüldükdə yazılır; uydurma rəqəm defoltdan pisdir, çünki niyəsi olmur.
    psm: int | None = None
    max_pages: int | None = None

    # KATALOQ DİZAYNI (`ingestion/layout.py:STYLES`). Rənglər və kəsik
    # həndəsəsi orada, ölçmənin aparıldığı yerdə saxlanılır - burada yalnız
    # ADI yazılır ki, iki fayl bir-birindən asılı olmasın.
    layout: str = "araz"
    force_ocr: bool = False
    use_selenium: bool = False

    @property
    def scrapeable(self) -> bool:
        """Avtomatik KATALOQ çəkilişi cəhdi mənalıdırmı?"""
        return self.status == ACTIVE and bool(self.page_url)

    @property
    def shoppable(self) -> bool:
        """
        MAĞAZA çəkilişi mümkündürmü?

        `status`-dan ASILI DEYİL: `status` kataloq mənbəyini təsvir edir.
        Bravonun kataloq mənbəyi yoxdur (`BLOCKED`), mağaza mənbəyi isə var -
        ikisini eyni bayrağa bağlasaydıq, işləyən mənbə bağlı görünərdi.
        """
        return bool(self.shop_url)


PROFILES: dict[str, StoreProfile] = {
    "araz": StoreProfile(
        slug="araz",
        fmt="pdf",
        status=ACTIVE,
        page_url="https://arazmarket.az/az/discount-magazine",
        # 54 SƏHİFƏ ÖLÇÜLÜB. Limitsiz çağırış GPU-suz maşında ~15 dəqiqə OCR
        # deməkdir; limit kiçik verilsə (20) məhsul sayı 188-dən 69-a düşür.
        max_pages=54,
        psm=6,          # vahid blok - kataloq kartları belə oxunur
        note="Endirim jurnalı: statik HTML səhifə, tək PDF, 54 səhifə (~9 MB).",
    ),
    "bravo": StoreProfile(
        slug="bravo",
        fmt="html",
        # KATALOQ mənbəyi hələ də yoxdur: bravosupermarket.az marketinq
        # saytıdır, `special-offers` səhifəsi Selenium ilə render edildikdə
        # də bir dənə məhsul/qiymət vermir (2026-09-10 ölçüldü).
        status=BLOCKED,
        page_url="https://umico.az/categories/4497-dukan",
        use_selenium=True,
        # MAĞAZA mənbəyi TAPILDI. Umico kateqoriyası Selenium ilə də «0 məhsul»
        # qaytardı (render problemi deyil - kateqoriya boşdur), Umico axtarışı
        # isə robots ilə qadağandır. Bravonun öz saytındakı «Onlayn market»
        # linki Wolt-a gedir və orada tam kataloq var. Ətraflı: `shop.py`.
        shop_url="https://wolt.com/az/aze/baku/venue/bravo-hypermarket-20-yanvar",
        note="Kataloq mənbəyi yoxdur (sayt marketinqdir). Qiymətlər onlayn "
             "mağazadan gəlir: Wolt məkanı, `source='site'` snapshot kimi.",
    ),
    "bazar-store": StoreProfile(
        slug="bazar-store",
        fmt="html",
        status=BLOCKED,
        page_url="https://bazarstore.az/",
        # Bütün sayt (robots.txt daxil) baxım elanı qaytarır; səhifədə cəmi
        # bir `mailto:` linki var. Sayt qayıdanda burada yalnız `status`
        # dəyişməlidir.
        #
        # TƏKRAR ÖLÇÜLDÜ 2026-09-10: vəziyyət DƏYİŞMƏYİB. `bazarstore.az`,
        # `www.bazarstore.az` və `/az` - üçü də eyni «yenilənmə işləri»
        # elanını qaytarır (378 simvol mətn). Wolt-da da yoxdur: Bakı ərzaq
        # siyahısındakı 177 məkanın heç biri Bazar Store deyil («bazar»
        # uyğunluqları meyvə-tərəvəz dükanlarıdır, məsələn `bazar1` =
        # «AQRO AZ Fruit & Vegetables»).
        note="Sayt baxımdadır: bütün ünvanlar «yenilənmə işləri» elanını "
             "qaytarır, çəkiləcək məhsul yoxdur. Wolt-da da mövcud deyil "
             "(2026-09-10 yoxlanıldı).",
    ),
    "rahat": StoreProfile(
        slug="rahat",
        fmt="pdf",
        # MƏNBƏ TAPILDI (2026-09-10). Əvvəl «tapılmayıb» yazılırdı; səbəb
        # saytın olmaması DEYİL, `<base href>` qüsuru idi - linklər tapılırdı,
        # amma səhifə ünvanına görə həll olunub 404 verirdi. Qüsur
        # `scraper.py:find_catalog_links()`-də bağlandı.
        status=ACTIVE,
        page_url="https://rahatmarket.az/az/aksiyalar/rahat-market",
        # 11 SƏHİFƏ ÖLÇÜLDÜ (5_18_avqust.pdf). Afişa PDF-i 1 səhifədir.
        # Limit qoymuruq - Arazdakı 54 səhifə ilə müqayisədə kiçikdir.
        max_pages=12,
        psm=6,          # vahid blok - kataloq kartları belə oxunur
        layout="rahat",
        note="Aksiyalar səhifəsində PDF kataloq: 1 səhifəlik afişa (3 MB) və "
             "11 səhifəlik jurnal (8 MB). İkisi də skan - OCR lazımdır.",
    ),
}


def profile_for(slug: str | None) -> StoreProfile | None:
    """Slug üzrə profil. Tanınmayan market üçün `None` (defolt ayarlar işləyir)."""
    if not slug:
        return None
    return PROFILES.get(slug.strip().lower())


def profile_for_store_name(name: str | None) -> StoreProfile | None:
    """
    Market ADINA görə profil - əl ilə yükləmə axını üçün.

    Yükləmə formasında istifadəçi ad yazır («Bravo», «Araz Market»), slug isə
    reyestrdə hesablanır. Ad → market → slug zənciri `app/stores.py`-dədir,
    yəni aliaslar («araz-market» = «araz») da işləyir.
    """
    if not name:
        return None
    # `slugify` YÜKLƏMƏ AXINININ ÖZ funksiyasıdır: market sətri bazada məhz
    # onun verdiyi slug ilə yaradılır. Burada başqa çevirmə işlətsək, profil
    # bazadakı marketdən FƏRQLİ açar üzrə axtarılardı.
    from ingestion.ingest import slugify

    from app.stores import market_for

    market = market_for(slugify(name))
    return PROFILES.get(market.slug) if market else None
