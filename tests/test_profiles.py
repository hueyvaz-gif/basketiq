"""
MARKET EMAL PROFİLLƏRİ (D14) — «adapter» qatı.

BU TESTLƏRİN TUTDUĞU SƏHV NÖVÜ: profil TAPILMIR və emal səssizcə ümumi
defoltla işləyir. Nəticə xəta deyil, sadəcə DAHA AZ DATA-dır - Araz üçün
`max_pages` unudulanda məhsul sayı 188-dən 69-a düşür və heç bir yerdə
xəbərdarlıq görünmür.

İkinci risk: uydurma mənbə. Ünvanı olmayan markete «mənbə var» kimi baxsaq,
avtomatik çəkiliş boş nəticə qaytarar və səbəb heç yerdə yazılmaz.
"""

import pytest

from app.stores import MARKETS
from ingestion.profiles import (
    ACTIVE,
    BLOCKED,
    MANUAL,
    PROFILES,
    profile_for,
    profile_for_store_name,
)
from ingestion.scraper import SOURCES, apply_profile


# --------------------------------------------------------------- reyestr


def test_hər_marketin_profili_var():
    """
    Reyestr ilə profil siyahısı TAM üst-üstə düşməlidir.

    Biri əlavə olunub digəri unudulsa, `profile_for()` `None` qaytarar və
    emal ümumi defoltla davam edər - yəni səhv yalnız nəticənin kasıblığında
    görünərdi.
    """
    assert set(PROFILES) == {market.slug for market in MARKETS}


def test_profilin_slugu_öz_açarı_ilə_eynidir():
    """Açarla sahə ayrılsa, `profile_for(slug)` başqa marketin ayarını verərdi."""
    for açar, profile in PROFILES.items():
        assert profile.slug == açar


@pytest.mark.parametrize("slug", sorted(PROFILES))
def test_hər_profilin_səbəbi_yazılıb(slug):
    """
    `note` boş qala bilməz. Admin panelində məhz o görünür: «bu market niyə
    boşdur?» sualının cavabı kodda deyil, ekranda olmalıdır.
    """
    assert PROFILES[slug].note.strip(), f"{slug} üçün səbəb yazılmayıb"


@pytest.mark.parametrize("slug", sorted(PROFILES))
def test_format_tanınan_dəyərdir(slug):
    assert PROFILES[slug].fmt in {"pdf", "image", "html"}


@pytest.mark.parametrize("slug", sorted(PROFILES))
def test_vəziyyət_tanınan_dəyərdir(slug):
    assert PROFILES[slug].status in {ACTIVE, MANUAL, BLOCKED}


# ------------------------------------------------------------ mənbə həqiqəti


def test_yalnız_işlək_mənbə_çəkilə_bilir():
    """
    `scrapeable` iki şərtin BİRLİKDƏ ödənməsidir: vəziyyət «active» VƏ ünvan
    var. Yalnız birinə baxsaydıq, ünvansız «active» market üçün çəkiliş
    başlayar və izahsız boş nəticə verərdi.
    """
    for profile in PROFILES.values():
        gözlənilir = profile.status == ACTIVE and bool(profile.page_url)
        assert profile.scrapeable is gözlənilir


def test_rahatın_mənbəyi_ölçülüb_və_qeydiyyatdadır():
    """
    2026-09-10-a QƏDƏR bu test əksini yoxlayırdı: «Rahat üçün mənbə
    tapılmayıb, `page_url` boş olmalıdır».

    FAKT DƏYİŞDİ. Mənbə var idi - `rahatmarket.az/az/aksiyalar/rahat-market`
    səhifəsində PDF kataloq. Onu görməyimizə mane olan saytın özü deyil,
    BİZİM QÜSURUMUZ idi: səhifə `<base href>` işlədir, `find_catalog_links()`
    isə onu nəzərə almırdı və ünvanlar 404-ə həll olunurdu
    (`tests/test_scraper.py:test_base_teqi_nezere_alinir`).

    Testin NİYYƏTİ dəyişmir: ünvan yalnız ÖLÇÜLDÜKDƏN sonra yazılır.
    """
    profile = profile_for("rahat")
    assert profile.page_url == "https://rahatmarket.az/az/aksiyalar/rahat-market"
    assert profile.status == ACTIVE
    assert profile.fmt == "pdf"


def test_mənbəsi_olmayan_market_uydurma_ünvan_almır():
    """
    Bazar Store-un saytı baxımdadır (2026-09-10-da təkrar ölçüldü, dəyişməyib)
    və Wolt-da da yoxdur. `status` bunu açıq deyir - uydurma ünvan «mənbə var»
    təəssüratı yaradar və səhv yalnız çəkiliş boş qayıdanda üzə çıxardı.
    """
    profile = profile_for("bazar-store")
    assert profile.status == BLOCKED
    assert profile.scrapeable is False
    assert "baxımdadır" in profile.note


def test_çəkilə_bilən_hər_profilin_scraper_qeydiyyatı_var():
    """
    `PROFILES` «necə oxumalı», `SOURCES` isə «haradan çəkməli» deməkdir.
    Biri digərindən qabağa keçsə, admin panelində işlək görünən market
    çəkiliş anında «naməlum mənbə» xətası verərdi.
    """
    for slug, profile in PROFILES.items():
        if profile.scrapeable:
            assert slug in SOURCES, f"{slug} çəkilə bilir, amma SOURCES-da yoxdur"


# --------------------------------------------------------------- ad → profil


@pytest.mark.parametrize(
    "ad,gözlənilən",
    [
        ("Araz", "araz"),
        ("Araz Market", "araz"),      # alias
        ("araz-market", "araz"),
        ("Bravo", "bravo"),
        ("Bazarstore", "bazar-store"),  # alias
        ("Bazar Store", "bazar-store"),
        ("Rahat Market", "rahat"),
    ],
)
def test_market_adı_profilə_bağlanır(ad, gözlənilən):
    """
    Yükləmə formasında istifadəçi AD yazır. Ad → slug çevirməsi yükləmə
    axınının öz `slugify`-ı ilə eyni olmalıdır, əks halda profil bazadakı
    marketdən FƏRQLİ açar üzrə axtarılar və heç vaxt tapılmazdı.
    """
    profile = profile_for_store_name(ad)
    assert profile is not None and profile.slug == gözlənilən


def test_tanınmayan_market_profilsiz_qalır():
    """Reyestrdən kənar ad üçün defolt ayarlar işləməlidir - xəta yox."""
    assert profile_for_store_name("Naməlum market") is None
    assert profile_for("yoxdur") is None
    assert profile_for(None) is None


# ------------------------------------------------------ profilin tətbiqi


def test_profil_boş_yeri_doldurur():
    """Çağıran heç nə verməyibsə, marketin ölçülmüş ayarı işə düşür."""
    max_pages, psm, force_ocr, selenium = apply_profile("araz", None, None, False, False)
    assert max_pages == 54, "Araz kataloqu 54 səhifədir - limit itsə məhsul sayı üç dəfə azalır"
    assert psm == 6


def test_çağıranın_açıq_dəyəri_üstündür():
    """
    Admin panelindən «3 səhifə» seçən istifadəçi məhz 3 səhifə gözləyir.
    Profil onu üstələsəydi, seçim səssizcə işləməzdi.
    """
    max_pages, psm, _, _ = apply_profile("araz", 3, 11, False, False)
    assert (max_pages, psm) == (3, 11)


def test_selenium_profildən_qalxır():
    """Umico JS ilə render olunur - bunu hər çağırışda əl ilə yazmaq lazım deyil."""
    *_, selenium = apply_profile("bravo", None, None, False, False)
    assert selenium is True


def test_profilsiz_market_dəyərləri_dəyişdirmir():
    assert apply_profile("yoxdur", 7, 4, True, True) == (7, 4, True, True)
