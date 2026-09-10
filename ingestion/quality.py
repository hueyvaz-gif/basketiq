"""
Qiymət sətirlərinin SAĞLAMLIQ yoxlaması — zibil UI-a çatmasın.

NİYƏ LAZIMDIR?
Zəncir belədir: qlyanslı kataloq → OCR → LLM → baza → ekran. Hər pillədə səhv
mümkündür və heç biri xəta atmır:

    «1.29» yerinə «129»          - OCR vergülü itirir
    «-2.90» köhnə qiymət kimi    - kataloqun bəzək rəqəmi qiymətə düşür
    «8009» qramaj kimi           - əslində «800 q» yazılıb

Belə sətir bazaya düşəndə ekranda İNANDIRICI görünür: rəqəmdir, formatı
düzgündür, kartda gözəl dayanır. Yalnız məzmunu yalandır. Ona görə yoxlama
BAZAYA YAZILARKƏN aparılır, ekranda yox.

NƏ EDİRİK: ATMIRIQ, NİŞANLAYIRIQ.
Şübhəli sətir silinsəydi, səhv yoxlanıla bilməzdi - nə oldu, niyə oldu?
Bunun əvəzinə sətir bazada qalır, üstündə isə bayraq olur. UI bayraqlı sətri
«bugünün endirimləri» siyahısına buraxmır, admin paneli isə onu ayrıca
göstərir: insan baxıb qərar verə bilir.

HƏDLƏR ÖLÇÜLÜB, UYDURULMAYIB - hər birinin izahı öz sabitindədir.
"""

from __future__ import annotations

import re
from statistics import median

# Endirim bu dərinlikdən keçirsə, sətir KARANTİNƏ düşür.
#
# BU, «SAXTA» HÖKMÜ DEYİL - insan baxışı üçün nişandır. `app/analytics.py`
# eyni ədədi işlədir və ikisi qəsdən bərabərdir: admin panelindəki karantin
# növbəsi ilə emal zənciri eyni sətirləri seçməlidir.
#
# İSTİFADƏÇİYƏ GÖSTƏRİLƏN HÖKM AYRIDIR (P4). Orada dərinlik heç nə sübut
# etmir: son istifadə tarixi yaxınlaşan məhsul real olaraq 70% ucuzlaşır.
# Hökm məhsulun ÖZ tarixçəsindən çıxarılır (`analytics.verify_claim`).
# Yəni dərin endirim həm karantində ola bilər, həm də ekranda «təsdiqlənib»
# görünə bilər - ziddiyyət deyil: biri data keyfiyyəti, digəri iddianın
# doğruluğudur.
DEEP_DISCOUNT = 0.55

# Qiymət məhsulun öz tarixçəsinin medianından bu qədər dəfə uzaqdırsa,
# statistik kənarlaşmadır.
#
# 4 dəfə niyə? Ərzaq qiyməti mövsümlə, endirimlə, qablaşdırma ilə 2-3 dəfə
# dəyişə bilir - bu, normaldır. 4 dəfədən yuxarı fərq isə praktiki olaraq ya
# OCR səhvidir (vergül itib), ya da başqa məhsulun qiyməti bu sətrə düşüb.
OUTLIER_RATIO = 4.0

# Tarixçə bundan qısadırsa, kənarlaşma hesablanmır: iki müşahidə ilə median
# heç nə demir və hər yeni qiymət «kənarlaşma» kimi görünərdi.
MIN_HISTORY = 3

# Vahid qiyməti kateqoriyanın medianından bu qədər dəfə uzaqdırsa şübhəlidir.
#
# 12 dəfə niyə bu qədər boldur? Kateqoriya daxilində real fərq böyükdür:
# «içkilər»də həm 0.60 ₼-lıq su, həm 180 ₼-lıq viski var. Hədd dar olsaydı,
# bahalı amma REAL məhsullar bayraqlanardı. Məqsəd nadir hallarda görünən
# açıq-aşkar zibili tutmaqdır, qiymət siyasətini mühakimə etmək yox.
UNIT_OUTLIER_RATIO = 12.0

# Bayraq açarları: UI-da tərcümə olunur (`app/static/i18n.js`, `flag.*`).
# ÇOXVARİANTLI KART: bir kartda bir neçə paket ölçüsü sadalanır və hansı
# qiymətin hansına aid olduğu BƏLLİ DEYİL.
#
# REAL SƏHVDƏN ÇIXIB (Rahat, 2026-09-10). Kataloq kartı belədir:
#     «Huggies Ultra Comfort N3 x 78  N4 x 66  N5 x 56»
# OCR sonuncu rəqəmi qiymət kimi götürdü: 126.53 ₼. Ekranda inandırıcı
# görünürdü - uşaq bezi bahalı ola bilər - amma yalan idi.
#
# NİYƏ MƏHZ BU NÜMUNƏ? Üç namizəd ölçüldü:
#     xam sətirdəki rəqəm sayı >= 3  -> Rahat 7/56, Araz 92/394  (23% - yararsız)
#     «N<rəqəm> x <say>» 2+ dəfə     -> Rahat 3/56, Araz 0/394
#     «<söz> x <say>» 2+ dəfə        -> Rahat 3/56, Araz 0/394
# Sonuncu seçildi: eyni dəqiqlik, amma «N» hərfini sabit yazmır. Söz həddi
# 6 hərfdir - 4 ilə ölçüldükdə eyni sətirləri tuturdu, amma «Paket x 12
# Qutu x 24» kimi yazılışı buraxırdı; 6 hərflə real nəticə dəyişmir
# (Rahat 3/56, Araz 0/394), əhatə isə genişlənir.
#
# Araz-da SIFIR yalançı müsbət verməsi vacibdir: bayraq nadir olmalıdır,
# əks halda karantin növbəsi dolur və insan ona baxmağı dayandırır.
MULTI_VARIANT_RE = re.compile(r"\b\w{1,6}\s*[xX×]\s*\d{2,}")
MIN_VARIANT_MATCHES = 2

FLAG_MULTI_VARIANT = "multiVariant"
FLAG_DEEP_DISCOUNT = "deepDiscount"
FLAG_PRICE_OUTLIER = "priceOutlier"
FLAG_UNIT_OUTLIER = "unitOutlier"


def discount_depth(price: float, old_price: float | None) -> float | None:
    """Endirim dərinliyi (0-1). Köhnə qiymət yoxdursa və ya kiçikdirsə None."""
    if not old_price or old_price <= price:
        return None
    return (old_price - price) / old_price


def check_price(
    *,
    price: float,
    old_price: float | None = None,
    history: list[float] | None = None,
    unit_price: float | None = None,
    category_median_unit: float | None = None,
    raw_line: str | None = None,
) -> list[str]:
    """
    Bir qiymət sətrini yoxlayır və BAYRAQ SİYAHISI qaytarır.

    Boş siyahı = sətir təmizdir. Funksiya bazaya toxunmur və heç nə atmır -
    yalnız qiymətləndirir; qərarı çağıran tərəf verir.
    """
    flags: list[str] = []

    # Çoxvariantlı kart: qiymət hansı ölçüyə aiddir - bilinmir.
    if raw_line and len(MULTI_VARIANT_RE.findall(raw_line)) >= MIN_VARIANT_MATCHES:
        flags.append(FLAG_MULTI_VARIANT)

    depth = discount_depth(price, old_price)
    if depth is not None and depth > DEEP_DISCOUNT:
        flags.append(FLAG_DEEP_DISCOUNT)

    # Tarixçə ilə müqayisə: qiymət öz məhsulunun medianından nə qədər uzaqdır?
    if history and len(history) >= MIN_HISTORY:
        orta = median(history)
        if orta > 0:
            nisbət = price / orta
            if nisbət > OUTLIER_RATIO or nisbət < 1 / OUTLIER_RATIO:
                flags.append(FLAG_PRICE_OUTLIER)

    # Kateqoriya norması ilə müqayisə: 1 kq / 1 l qiyməti nə qədər uzaqdır?
    if unit_price and category_median_unit and category_median_unit > 0:
        nisbət = unit_price / category_median_unit
        if nisbət > UNIT_OUTLIER_RATIO or nisbət < 1 / UNIT_OUTLIER_RATIO:
            flags.append(FLAG_UNIT_OUTLIER)

    return flags


def needs_review(flags: list[str] | None) -> bool:
    """Bayraqlı sətir insan baxışı tələb edir."""
    return bool(flags)
