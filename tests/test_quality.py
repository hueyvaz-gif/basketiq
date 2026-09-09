"""
Qiymət sətirlərinin sağlamlıq yoxlaması (`ingestion.quality`) — C12.

BU YOXLAMANIN TUTDUĞU SƏHV HEÇ VAXT XƏTA ATMIR. OCR vergülü itirəndə
«1.29» → «129» olur: rəqəmdir, formatı düzgündür, kartda gözəl dayanır və
ekranda tamamilə İNANDIRICI görünür. Yeganə problemi odur ki, yalandır.

Ona görə testlər iki sualı ayrı-ayrı yoxlayır:

  1. HƏDD DOĞRU YERDƏDİRMİ — dar hədd real bahalı məhsulu (viski, ət)
     «zibil» elan edər, gen hədd isə heç nə tutmaz;
  2. NİŞANLANMIŞ SƏTİR EKRANA ÇIXIRMI — yoxlama bazada işləyib UI-da
     nəzərə alınmasa, bütün zəhmət görünməz qalır.

Sətir ATILMIR, nişanlanır: silinsəydi, səhvin niyə baş verdiyini araşdırmaq
mümkün olmazdı.
"""

import json
import uuid

import pytest

from app.analytics import SUSPICIOUS_DEPTH
from app.catalog import todays_deals
from app.db import db_cursor, get_connection
from app.models import ExtractedProduct
from ingestion.pipeline import save_products
from ingestion.quality import (
    DEEP_DISCOUNT,
    FLAG_DEEP_DISCOUNT,
    FLAG_PRICE_OUTLIER,
    FLAG_UNIT_OUTLIER,
    MIN_HISTORY,
    OUTLIER_RATIO,
    UNIT_OUTLIER_RATIO,
    check_price,
    discount_depth,
    needs_review,
)


# ============================================================================
# HƏDLƏR
# ============================================================================


def test_karantin_həddi_iki_yerdə_eynidir():
    """
    Hər iki ədəd KARANTİN triggeridir: `quality.DEEP_DISCOUNT` emal zəncirində
    nişanlayır, `analytics.SUSPICIOUS_DEPTH` isə admin panelinin eyni sətirləri
    seçməsini təmin edir. Ayrılsaydılar, emal nişanladığı sətri admin növbədə
    görməzdi.

    DİQQƏT (P4): bu ədəd artıq İSTİFADƏÇİYƏ GÖSTƏRİLƏN hökmü təyin etmir.
    Dərin endirim öz-özünə «şübhəli» deyil - hökm məhsulun tarixçəsindən
    çıxarılır. Yəni sətir eyni anda karantində və ekranda «təsdiqlənib»
    ola bilər: biri data keyfiyyəti, digəri iddianın doğruluğudur.
    """
    assert DEEP_DISCOUNT == SUSPICIOUS_DEPTH


@pytest.mark.parametrize(
    "price,old_price,gözlənilir",
    [
        (3.00, 10.00, True),    # 70% — açıq-aşkar dərin
        (4.40, 10.00, True),    # 56% — hədddən bir addım yuxarı
        (4.50, 10.00, False),   # 55% — HƏDDİN ÖZÜ təmiz sayılır (ciddi «>»)
        (5.00, 10.00, False),   # 50% — normal bayram endirimi
        (9.00, 10.00, False),   # 10%
    ],
)
def test_dərin_endirim_yalnız_hədddən_yuxarıda_nişanlanır(price, old_price, gözlənilir):
    flags = check_price(price=price, old_price=old_price)
    assert (FLAG_DEEP_DISCOUNT in flags) is gözlənilir


@pytest.mark.parametrize("old_price", [None, 0, 5.00, 4.00])
def test_köhnə_qiymət_yoxdursa_dərinlik_hesablanmır(old_price):
    """
    Endirimi olmayan sətir (köhnə qiymət yoxdur və ya yenidən kiçikdir)
    endirim bayrağı ALA BİLMƏZ — əks halda kataloqun bütün adi sətirləri
    karantinə düşərdi.
    """
    assert discount_depth(5.00, old_price) is None
    assert FLAG_DEEP_DISCOUNT not in check_price(price=5.00, old_price=old_price)


# ============================================================================
# TARİXÇƏ İLƏ MÜQAYİSƏ
# ============================================================================


def test_tarixçə_qısadırsa_kənarlaşma_hesablanmır():
    """
    İki müşahidə ilə median heç nə demir: yeni market üçün İLK qiymətlər
    həmişə «kənarlaşma» kimi görünərdi və bütün kataloq karantinə düşərdi.
    """
    qısa = [2.00] * (MIN_HISTORY - 1)
    assert check_price(price=100.00, history=qısa) == []


def test_medianın_dəfələrlə_üstü_kənarlaşmadır():
    """«1.29» → «129» halı: vergül itib, qiymət 100 dəfə böyüyüb."""
    flags = check_price(price=129.00, history=[1.29, 1.35, 1.19, 1.29])
    assert FLAG_PRICE_OUTLIER in flags


def test_medianın_dəfələrlə_altı_da_kənarlaşmadır():
    """
    Səhv yalnız yuxarı işləmir: qonşu sətrin qiyməti bu məhsula düşəndə
    rəqəm KİÇİLİR. Tək tərəfli yoxlama halların yarısını buraxardı.
    """
    flags = check_price(price=0.05, history=[4.90, 5.10, 5.00, 4.95])
    assert FLAG_PRICE_OUTLIER in flags


def test_mövsümi_iki_dəfə_fərq_normaldır():
    """
    Ərzaq qiyməti mövsümlə, endirimlə, qablaşdırma ilə 2-3 dəfə dəyişir.
    Hədd bu qədər dar olsaydı, real endirimlərin yarısı karantində qalardı.
    """
    orta = 5.00
    hədddən_aşağı = orta * (OUTLIER_RATIO - 1.5)
    assert check_price(price=hədddən_aşağı, history=[orta] * MIN_HISTORY) == []


# ============================================================================
# KATEQORİYA NORMASI
# ============================================================================


def test_vahid_qiyməti_kateqoriya_normasından_çox_uzaqdırsa_nişanlanır():
    """«800 q» → «8009» halı: qramaj səhv oxunanda ₼/kq gülünc dərəcədə düşür."""
    flags = check_price(price=4.00, unit_price=0.05, category_median_unit=5.00)
    assert FLAG_UNIT_OUTLIER in flags


def test_bahalı_amma_real_məhsul_nişanlanmır():
    """
    Bir kateqoriyada həm 0.60 ₼-lıq su, həm 180 ₼-lıq viski var. Hədd
    dar olsaydı, ən bahalı REAL məhsullar sistematik olaraq karantinə
    düşərdi — istifadəçi isə onları axtarışda görməli idi.
    """
    kənarda = 5.00 * (UNIT_OUTLIER_RATIO - 2)
    assert check_price(price=90.00, unit_price=kənarda, category_median_unit=5.00) == []


def test_norma_yoxdursa_müqayisə_edilmir():
    """Yeni kateqoriyanın medianı hələ yoxdur — bu, şübhə səbəbi deyil."""
    assert check_price(price=4.00, unit_price=0.05, category_median_unit=None) == []
    assert check_price(price=4.00, unit_price=None, category_median_unit=5.00) == []


# ============================================================================
# YEKUN QƏRAR
# ============================================================================


def test_təmiz_sətir_bayraqsız_qalır():
    flags = check_price(
        price=4.50,
        old_price=5.00,
        history=[4.40, 4.60, 4.55],
        unit_price=4.50,
        category_median_unit=5.00,
    )
    assert flags == []
    assert needs_review(flags) is False


def test_bir_sətir_bir_neçə_bayraq_ala_bilir():
    """
    Bayraqlar bir-birini əvəz etmir: səbəblərin hamısı saxlanır ki, admin
    panelində «niyə şübhəlidir?» sualının cavabı görünsün.
    """
    flags = check_price(
        price=1.00,
        old_price=20.00,                 # 95% endirim
        history=[50.00, 52.00, 48.00],   # medianın 50 dəfə altı
        unit_price=0.01,
        category_median_unit=5.00,
    )
    assert set(flags) == {FLAG_DEEP_DISCOUNT, FLAG_PRICE_OUTLIER, FLAG_UNIT_OUTLIER}
    assert needs_review(flags) is True


# ============================================================================
# EMAL ZƏNCİRİ VƏ EKRAN
# ============================================================================


def _market(slug: str, name: str) -> int:
    with db_cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO stores (slug, name) VALUES (?, ?)", (slug, name))
        return cur.lastrowid


def _kataloq(store_id: int) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, status) "
            "VALUES (?, ?, ?, 'parsed')",
            (store_id, uuid.uuid4().hex, "quality-test.pdf"),
        )
        return cur.lastrowid


def _məhsul(key: str, name: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key) VALUES (?, ?, ?)",
            (f"{key}|{uuid.uuid4().hex[:6]}", name, key),
        )
        return cur.lastrowid


def _qrup(product_id: int) -> str:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT group_key FROM products WHERE id = ?", (product_id,)
        ).fetchone()["group_key"]
    finally:
        conn.close()


def test_emal_zənciri_bayrağı_bazaya_yazır():
    """
    Yoxlama ekranda deyil, BAZAYA YAZILARKƏN aparılır: sətir bir dəfə
    qiymətləndirilir və nəticə orada qalır. Ekran tərəfdə etsəydik, hər
    səhifə açılışında yenidən hesablanardı və admin «nə vaxt nişanlandı?»
    sualına cavab tapa bilməzdi.
    """
    store_id = _market("araz", "Araz")
    catalog_id = _kataloq(store_id)
    key = f"keyfiyyet|zencir|{uuid.uuid4().hex[:6]}"

    save_products(
        [
            ExtractedProduct(
                name="dərin endirimli sətir",
                price=1.00,
                old_price=10.00,          # 90% — dərin
                canonical_key=key,
                raw_line="dərin endirimli sətir 1.00",
            )
        ],
        store_id,
        catalog_id,
    )

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT pr.flags FROM prices pr JOIN products p ON p.id = pr.product_id "
            "WHERE p.canonical_key = ?",
            (key,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None, "qiymət sətri yazılmadı"
    assert json.loads(row["flags"]) == [FLAG_DEEP_DISCOUNT]


def test_nişanlı_sətir_bugünün_endirimlərinə_düşmür():
    """
    Karantinin BÜTÜN mənası budur. Nişan bazada qalıb ekrana təsir
    etməsəydi, şübhəli sətir yenə də siyahının başında dayanardı — çünki
    sıralama məhz faizə görədir və şübhəli sətirlərin faizi ən böyükdür.
    """
    store_id = _market("araz", "Araz")
    catalog_id = _kataloq(store_id)

    təmiz = _məhsul(f"keyfiyyet|temiz|{uuid.uuid4().hex[:6]}", "təmiz endirim")
    nişanlı = _məhsul(f"keyfiyyet|nisanli|{uuid.uuid4().hex[:6]}", "nişanlı endirim")

    with db_cursor() as cur:
        for pid, flags in ((təmiz, None), (nişanlı, json.dumps([FLAG_DEEP_DISCOUNT]))):
            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price, old_price, "
                "                    flags, seen_at) "
                "VALUES (?, ?, ?, 4.00, 10.00, ?, datetime('now'))",
                (pid, store_id, catalog_id, flags),
            )

    açarlar = {d["group_key"] for d in todays_deals(limit=100)["items"]}

    # Eyni faiz (60%), eyni market, eyni kataloq — YEGANƏ fərq bayraqdır.
    assert _qrup(təmiz) in açarlar, "təmiz sətir siyahıdan düşdü — süzgəc çox geniş"
    assert _qrup(nişanlı) not in açarlar, "nişanlı sətir siyahıya çıxdı — karantin işləmir"
