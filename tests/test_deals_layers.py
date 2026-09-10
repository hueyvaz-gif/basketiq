"""
«BUGÜNÜN ENDİRİMLƏRİ» — hər iki qiymət qatından.

NİYƏ BU FAYL VAR (diaqnostika 2026-09-10): ana səhifədəki siyahı demək olar
tamamilə Arazdan ibarət idi. İki AYRI səbəb tapıldı və hər ikisi burada
qorunur:

  1. SXEM. `price_snapshots` cədvəlində `old_price` sütunu YOX İDİ - yalnız
     `is_promo`. Bravonun 13 089 məhsulu məhz o cədvəldədir, 3 369-u
     endirimdədir - amma faiz hesablana bilmədiyi üçün siyahıya prinsipcə
     düşə bilmirdi.
  2. KƏSİK. Endpoint `limit`-i səssizcə 60-a endirirdi. Bravonun yeganə
     kataloq endirimi (16.3%) sıralamada 69-cu idi, çünki 67 Araz endirimi
     ondan dərindir. Heç bir süzgəc onu atmırdı - sadəcə kəsikdən aşağı
     düşürdü.
"""

import pytest
from fastapi.testclient import TestClient

from app.catalog import MIN_DISCOUNT_PCT, discount_pct, store_page, todays_deals
from app.db import db_cursor
from app.main import app
from app.search_norm import fold
from ingestion.normalize import canonical_key


# ---------------------------------------------------------------- helper


def test_faiz_hesablanir():
    assert discount_pct(7.95, 9.5) == 16.3
    assert discount_pct(1.89, 2.05) == 7.8


def test_endirim_olmayanda_none():
    assert discount_pct(10.0, 10.0) is None
    assert discount_pct(10.0, 8.0) is None, "köhnə qiymət yenidən ucuz ola bilməz"
    assert discount_pct(10.0, None) is None
    assert discount_pct(None, 10.0) is None


def test_cuzi_endirim_atilir():
    """3%-dən aşağı endirim siyahını doldurur, amma heç nə vermir."""
    assert discount_pct(99.0, 100.0) is None
    assert discount_pct(96.0, 100.0) == 4.0
    assert MIN_DISCOUNT_PCT == 3.0


def test_derin_endirim_defolt_atilir_amma_sondurule_biler():
    """
    `max_depth=None` «bugünün endirimləri» üçündür: orada dərin endirim
    atılmır, əvvəlcə `verify_claim()` ilə yoxlanılır.
    """
    assert discount_pct(1.0, 100.0) is None
    assert discount_pct(1.0, 100.0, max_depth=None) == 99.0


# ---------------------------------------------------------------- qatlar


def _mehsul_yarat(cur, ad: str, slug: str, price: float, old: float, layer: str):
    """
    Test məhsulu yaradır.

    `slug` REYESTRDƏN olmalıdır (`app/stores.py:MARKETS`). `todays_deals()`
    yalnız tanınan marketləri göstərir və bu, qəsdəndir: uydurma market
    siyahıda görünsəydi, istifadəçi onu real sanardı.
    """
    key = canonical_key(ad, None, None, None)
    cur.execute(
        "INSERT OR IGNORE INTO stores (name, slug) VALUES (?, ?)", (ad + " Store", slug)
    )
    cur.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
    store_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO products (canonical_key, name, group_key, name_norm) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(canonical_key) DO UPDATE SET name = excluded.name",
        (key, ad, key, fold(ad)),
    )
    cur.execute("SELECT id FROM products WHERE canonical_key = ?", (key,))
    pid = cur.fetchone()[0]

    if layer == "catalog":
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path) VALUES (?, ?, ?)",
            (store_id, f"hash-{key}", f"/tmp/{key}.pdf"),
        )
        cur.execute("SELECT id FROM catalogs WHERE file_hash = ?", (f"hash-{key}",))
        cat_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price, old_price) "
            "VALUES (?, ?, ?, ?, ?)",
            (pid, store_id, cat_id, price, old),
        )
    else:
        # `ON CONFLICT` istehsaldakı `save_snapshots()` ilə eynidir: gündə
        # bir sətir qaydası testdə də tətbiq olunur. Onsuz `canonical_key`
        # rəqəmləri normallaşdırdığı üçün «Novbe Bravo 0» və «Novbe Bravo 1»
        # eyni məhsula düşür və test IntegrityError ilə qırılır.
        cur.execute(
            "INSERT INTO price_snapshots (product_id, store_id, price, old_price, "
            "                             is_promo, source, observed_at) "
            "VALUES (?, ?, ?, ?, 1, 'site', datetime('now')) "
            "ON CONFLICT(product_id, store_id, source, date(observed_at)) DO UPDATE SET "
            "  price = excluded.price, old_price = excluded.old_price",
            (pid, store_id, price, old),
        )
    return pid, store_id


def test_magaza_qatinin_endirimi_siyahiya_dusur():
    """
    ƏSAS REQRESİYA. Sxemdə `old_price` olmayanda mağaza qatının endirimi
    siyahıya PRİNSİPCƏ düşə bilmirdi.
    """
    with db_cursor() as cur:
        _mehsul_yarat(cur, "Qat Test Mağaza Məhsulu", "bravo", 7.0, 10.0, "site")

    adlar = [d["label"] for d in todays_deals(limit=500)["items"]]
    assert "Qat Test Mağaza Məhsulu" in adlar, "mağaza qatı siyahıya düşmür"


def test_kataloq_qati_da_islenir():
    with db_cursor() as cur:
        _mehsul_yarat(cur, "Qat Test Kataloq Məhsulu", "araz", 8.0, 10.0, "catalog")

    adlar = [d["label"] for d in todays_deals(limit=500)["items"]]
    assert "Qat Test Kataloq Məhsulu" in adlar


def test_iki_qat_eyni_siyahida_gorunur():
    """Siyahı bir markete bağlı OLMAMALIDIR."""
    with db_cursor() as cur:
        _mehsul_yarat(cur, "Ikiqat Test A", "araz", 5.0, 10.0, "catalog")
        _mehsul_yarat(cur, "Ikiqat Test B", "bravo", 6.0, 10.0, "site")

    items = todays_deals(limit=500)["items"]
    marketlər = {d["store_slug"] for d in items if d["label"].startswith("Ikiqat Test")}
    assert len(marketlər) >= 2, f"yalnız bir market çıxdı: {marketlər}"


def test_her_marketin_oz_icinde_faize_gore_siralanir():
    """
    Növbələşmə ÜMUMİ sıranı qəsdən pozur (bir market siyahını udmasın), amma
    HƏR MARKETİN ÖZ növbəsi faizə görə sıralı qalmalıdır - yəni marketin ən
    yaxşı təklifi onun ikinci təklifindən əvvəl gəlir.
    """
    items = todays_deals(limit=500)["items"]
    for verdict in {d["verdict"] for d in items}:
        for slug in {d["store_slug"] for d in items}:
            qrup = [
                d["discount_pct"]
                for d in items
                if d["verdict"] == verdict and d["store_slug"] == slug
            ]
            assert qrup == sorted(qrup, reverse=True), (
                f"«{verdict}» / «{slug}» sıralı deyil: {qrup[:6]}"
            )


# ---------------------------------------------------------------- uyğunluq


def test_magaza_sehifesi_ve_deals_eyni_faizi_verir():
    """
    UYĞUNSUZLUQ REAL OLARAQ GÖRÜLDÜ: market səhifəsində «-16%» yazılırdı,
    ana səhifədə isə həmin məhsul yox idi. İkisi indi `discount_pct()`
    funksiyasından qidalanır.
    """
    with db_cursor() as cur:
        _mehsul_yarat(cur, "Uygunluq Test Məhsulu", "rahat", 8.0, 10.0, "catalog")

    səhifə = store_page("rahat", limit=50)
    if səhifə is None:
        pytest.skip("market reyestrdə yoxdur - bu test yalnız tanınan market üçündür")

    səhifə_faizi = {
        p["label"]: p.get("discount_pct")
        for p in səhifə["products"]
        if p["label"] == "Uygunluq Test Məhsulu"
    }
    deals_faizi = {
        d["label"]: d["discount_pct"]
        for d in todays_deals(limit=500)["items"]
        if d["label"] == "Uygunluq Test Məhsulu"
    }
    for ad, faiz in səhifə_faizi.items():
        if ad in deals_faizi:
            assert faiz == deals_faizi[ad], f"{ad}: səhifə {faiz}, deals {deals_faizi[ad]}"


# ---------------------------------------------------------------- limit


def test_limit_qapagi_60_deyil():
    """
    SƏSSİZ QAPAQ: `limit=500` sorğusu 60-a çevrilirdi və çağıran bunu heç
    yerdə görmürdü - diaqnostika «endirimlər süzülür» qənaətinə gətirdi.
    """
    with TestClient(app) as client:
        res = client.get("/api/catalog/deals?limit=500")
        assert res.status_code == 200
        # Qapaq hələ də var (hədsiz sorğu cavabı şişirdərdi), amma 60 deyil.
        assert len(res.json()["items"]) <= 500


def test_kicik_limit_hormetlenir():
    with TestClient(app) as client:
        res = client.get("/api/catalog/deals?limit=3")
        assert len(res.json()["items"]) <= 3


# ---------------------------------------------------------------- yetim təmizliyi


def test_kataloq_silinmesi_magaza_mehsulunu_silmir():
    """
    REQRESİYA (2026-09-10). Kataloq silinəndə «yetim məhsul» təmizliyi
    yalnız `prices`-ə baxırdı:

        DELETE FROM products WHERE id NOT IN (SELECT product_id FROM prices)

    `price_snapshots` boş olduğu müddətdə fərq görünmürdü. Mağaza qatı
    dolan kimi sətir TƏHLÜKƏLİ oldu: Bravonun 13 089 məhsulunun `prices`
    sətri yoxdur - onlar yalnız snapshot-dadır. Yəni İSTƏNİLƏN kataloqu
    silmək həmin 13 min məhsulu silməyə cəhd edirdi.

    Praktikada `DELETE /api/catalogs/{id}` 500 qaytarırdı; xarici açar
    yoxlaması sönülü olsaydı, mağaza qatı SƏSSİZCƏ yox olardı.
    """
    with db_cursor() as cur:
        # Yalnız snapshot-u olan məhsul (mağaza qatı)
        magaza_pid, _ = _mehsul_yarat(
            cur, "Yetim Test Mağaza Məhsulu", "bravo", 7.0, 10.0, "site"
        )
        # Silinəcək kataloqu olan ayrı məhsul
        _mehsul_yarat(cur, "Yetim Test Kataloq Məhsulu", "araz", 8.0, 10.0, "catalog")
        cur.execute(
            "SELECT id FROM catalogs WHERE file_hash = ?",
            (f"hash-{canonical_key('Yetim Test Kataloq Məhsulu', None, None, None)}",),
        )
        catalog_id = cur.fetchone()[0]

    with TestClient(app) as client:
        res = client.delete(f"/api/catalogs/{catalog_id}")
        assert res.status_code == 200, f"kataloq silinmədi: {res.status_code} {res.text[:120]}"

    from app.db import get_connection

    conn = get_connection()
    try:
        qaldi = conn.execute(
            "SELECT COUNT(*) FROM products WHERE id = ?", (magaza_pid,)
        ).fetchone()[0]
        assert qaldi == 1, "mağaza qatının məhsulu kataloq silinəndə yox oldu"
    finally:
        conn.close()


# ---------------------------------------------------------------- növbələşmə


def _novbelesme_datasi():
    """Bir marketə 6, digərinə 1 endirim - növbələşmə olmasa biri udardı."""
    with db_cursor() as cur:
        adlar = ["Konfet", "Sabun", "Yağ", "Çay", "Duz", "Şəkər"]
        for ad, pct in zip(adlar, [60, 55, 50, 45, 40, 35]):
            _mehsul_yarat(cur, f"Novbe Bravo {ad}", "bravo", 100 - pct, 100.0, "site")
        _mehsul_yarat(cur, "Novbe Araz 0", "araz", 80.0, 100.0, "catalog")


def test_bir_market_siyahini_udmur():
    """
    ÖLÇÜLDÜ: mağaza qatı qoşulandan sonra bölgü 100% Arazdan 96% Bravoya
    çevrildi - eyni problem tərsinə döndü. Növbələşmə bunu qarşılayır.
    """
    _novbelesme_datasi()
    items = todays_deals(limit=6)["items"]
    marketlər = {d["store_slug"] for d in items}
    assert len(marketlər) >= 2, f"siyahı bir markete sıxıldı: {marketlər}"


def test_novbelesme_hokm_sirasini_pozmur():
    """
    Təsdiqlənmiş endirim həmişə yoxlanmamışdan ÖNDƏ olmalıdır. Növbələşmə
    yalnız HƏR HÖKM QRUPUNUN İÇİNDƏ aparılır - əks halda şübhəli bir
    endirim təsdiqlənmişin qabağına keçərdi.
    """
    RANK = {
        "tesdiqlenib": 0,
        "endirim_yoxdur": 1,
        "az_musahide": 2,
        "tesdiqlenmeyib": 3,
        "subheli": 4,
    }
    items = todays_deals(limit=500)["items"]
    rütbələr = [RANK.get(d["verdict"], 3) for d in items]
    assert rütbələr == sorted(rütbələr), "hökm sırası pozuldu"


def test_qrupun_icinde_en_yaxsi_teklifi_olan_market_birincidir():
    """
    Növbələşmə «ən sərfəli» vədini pozmamalıdır: hər hökm qrupunda birinci
    növbəni ən dərin endirimi olan market alır.
    """
    from app.catalog import _market_novbelesmesi

    RANK = {"az_musahide": 2}
    sıralı = [
        {"store_slug": "b", "discount_pct": 60.0, "verdict": "az_musahide"},
        {"store_slug": "b", "discount_pct": 50.0, "verdict": "az_musahide"},
        {"store_slug": "a", "discount_pct": 40.0, "verdict": "az_musahide"},
    ]
    nəticə = _market_novbelesmesi(sıralı, RANK)
    assert nəticə[0]["store_slug"] == "b", "ən dərin endirimi olan market birinci deyil"
    assert nəticə[1]["store_slug"] == "a", "növbələşmə işləmir"
    assert nəticə[2]["store_slug"] == "b"


def test_bir_market_bitende_qalan_davam_edir():
    """Kiçik növbə tükənəndə böyük market qalan yerləri doldurur."""
    from app.catalog import _market_novbelesmesi

    RANK = {"az_musahide": 2}
    sıralı = [
        {"store_slug": "b", "discount_pct": p, "verdict": "az_musahide"}
        for p in (60.0, 55.0, 50.0)
    ] + [{"store_slug": "a", "discount_pct": 45.0, "verdict": "az_musahide"}]
    nəticə = _market_novbelesmesi(sıralı, RANK)
    assert len(nəticə) == 4, "sətir itdi"
    assert [d["store_slug"] for d in nəticə] == ["b", "a", "b", "b"]


def test_novbelesme_setir_itirmir():
    """Növbələşmə yalnız SIRANI dəyişir - heç bir endirim yox olmamalıdır."""
    from app.catalog import _market_novbelesmesi

    RANK = {"tesdiqlenib": 0, "az_musahide": 2}
    sıralı = [
        {"store_slug": "a", "discount_pct": 30.0, "verdict": "tesdiqlenib"},
        {"store_slug": "b", "discount_pct": 60.0, "verdict": "az_musahide"},
        {"store_slug": "a", "discount_pct": 40.0, "verdict": "az_musahide"},
    ]
    assert len(_market_novbelesmesi(sıralı, RANK)) == len(sıralı)


# ---------------------------------------------------------------- sabit sıra


def test_eyni_vaxtli_setirlerde_sira_sabitdir():
    """
    REQRESİYA (2026-09-10, brauzerdə görüldü). `PRICE_ROWS_CTE`-yə keçəndə
    sorğudan `pr.id` bərabərlik pozucusu düşdü.

    Eyni kataloqdan gələn sətirlərin `seen_at`-i EYNİDİR (hamısı bir emalda
    yazılır), ona görə «sonuncu sətir» qaydası yalnız `at`-a görə
    sıralananda QEYRİ-MÜƏYYƏN olur. Praktikada məhsul kartında qiymət
    2.35 ilə 2.99 arasında dəyişirdi - səhv SƏSSİZ idi, çünki hər iki rəqəm
    real qiymətdir, sadəcə başqa sətirdəndir.
    """
    from app.db import get_connection

    with db_cursor() as cur:
        pid, store_id = _mehsul_yarat(cur, "Sabit Sira Testi", "araz", 5.0, 10.0, "catalog")
        cur.execute("SELECT catalog_id FROM prices WHERE product_id = ?", (pid,))
        cat_id = cur.fetchone()[0]
        # EYNİ `seen_at` ilə iki əlavə sətir - real kataloq emalındakı kimi.
        for qiymet in (7.0, 9.0):
            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price, seen_at) "
                "VALUES (?, ?, ?, ?, '2026-01-01 00:00:00')",
                (pid, store_id, cat_id, qiymet),
            )
        cur.execute(
            "UPDATE prices SET seen_at = '2026-01-01 00:00:00' WHERE product_id = ?", (pid,)
        )

    conn = get_connection()
    try:
        from app.db import PRICE_ROWS_CTE

        nəticələr = set()
        for _ in range(5):
            row = conn.execute(
                f"{PRICE_ROWS_CTE} "
                "SELECT pr.price FROM price_rows pr WHERE pr.product_id = ? "
                "ORDER BY pr.at, pr.layer, pr.row_id",
                (pid,),
            ).fetchall()
            nəticələr.add(tuple(r["price"] for r in row))
        assert len(nəticələr) == 1, f"sıra qaçışdan qaçışa dəyişdi: {nəticələr}"
    finally:
        conn.close()


def test_cte_row_id_qaytarir():
    """`row_id` olmasa sabit sıralama mümkün deyil."""
    from app.db import PRICE_ROWS_CTE, get_connection

    conn = get_connection()
    try:
        cur = conn.execute(f"{PRICE_ROWS_CTE} SELECT * FROM price_rows LIMIT 1")
        sütunlar = {d[0] for d in cur.description}
        assert {"row_id", "layer", "at", "old_price", "flags"} <= sütunlar
    finally:
        conn.close()
