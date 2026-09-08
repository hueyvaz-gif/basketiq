"""
`price_snapshots` cədvəli və market birləşdirmə miqrasiyasının testləri.

Bu testlər BAZANIN ÖZ QAYDALARINI yoxlayır - yəni kod səhv yazsa da bazanın
onu buraxmadığını. Səbəb: gündəlik çəkiliş avtomatik işləyəcək, orada "eyni
məhsulu iki dəfə yazdıq" səhvi səssiz keçsə, tarixçə qrafiki və endirim
yoxlaması yanlış rəqəm göstərər.
"""

import sqlite3
import uuid

import pytest

from app.db import _merge_duplicate_stores, db_cursor, get_connection, init_db


@pytest.fixture
def store_and_product():
    """
    Bir market və bir məhsul yaradır, id-lərini qaytarır.

    Slug/açar TƏSADÜFİDİR: `conftest.py` bazanı sessiyada BİR DƏFƏ qurur, yəni
    testlər eyni baza üzərində işləyir. Sabit ad işlətsək ikinci test
    `UNIQUE constraint failed: stores.slug` ilə düşərdi.
    """
    tag = uuid.uuid4().hex[:8]
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO stores (slug, name) VALUES (?, ?)",
            (f"t-snap-{tag}", f"Snapshot Market {tag}"),
        )
        store_id = cur.lastrowid
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key) VALUES (?, ?, ?)",
            (f"snap|sud|{tag}", "Snapshot süd", f"snap|sud|{tag}"),
        )
        product_id = cur.lastrowid
    return store_id, product_id


def _wipe_araz_stores() -> None:
    """`araz` / `araz-market` sətirlərini asılı datası ilə birlikdə silir."""
    conn = get_connection()
    try:
        ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM stores WHERE slug IN ('araz', 'araz-market')"
            )
        ]
        for store_id in ids:
            for table in ("price_snapshots", "prices", "catalogs"):
                conn.execute(f"DELETE FROM {table} WHERE store_id = ?", (store_id,))
            conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def temiz_araz():
    """Birləşdirmə testləri `araz*` adlarını işlədir - əvvəl və sonra təmizlənir."""
    _wipe_araz_stores()
    yield
    _wipe_araz_stores()


def _insert(cur, product_id, store_id, price, source, observed_at, is_promo=0):
    cur.execute(
        "INSERT INTO price_snapshots "
        "(product_id, store_id, price, is_promo, source, observed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (product_id, store_id, price, is_promo, source, observed_at),
    )


# ------------------------------------------------------------- gündə bir sətir


def test_eyni_gun_ikinci_yazi_unikal_indekslə_tutulur(store_and_product):
    """
    Tapşırığın tələbi: eyni gün iki dəfə yazmaq cəhdi tutulmalıdır.

    Vaxt möhürləri FƏRQLİDİR (09:00 və 18:30) - yəni indeks sütunun özünə
    qoyulsaydı bu test keçməzdi. `date(observed_at)` üzrə ifadəli indeks
    məhz bunun üçündür.
    """
    store_id, product_id = store_and_product
    with db_cursor() as cur:
        _insert(cur, product_id, store_id, 1.89, "site", "2026-09-08T09:00:00")

    with pytest.raises(sqlite3.IntegrityError):
        with db_cursor() as cur:
            _insert(cur, product_id, store_id, 1.95, "site", "2026-09-08T18:30:00")


def test_ertesi_gun_yeni_setir_yazilir(store_and_product):
    """Sətirlər üstünə yazılmır - hər gün öz sətrini alır."""
    store_id, product_id = store_and_product
    with db_cursor() as cur:
        _insert(cur, product_id, store_id, 1.89, "site", "2026-09-08T09:00:00")
        _insert(cur, product_id, store_id, 1.95, "site", "2026-09-09T09:00:00")

    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) c FROM price_snapshots WHERE product_id = ?",
            (product_id,),
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 2


def test_sayt_ve_kataloq_eyni_gunde_toqqusmur(store_and_product):
    """
    `source` unikal açarın bir hissəsidir.

    Eyni gün həm saytdan, həm kataloqdan qiymət gələ bilər - bunlar İKİ AYRI
    müşahidədir və bir-birini əvəz etməməlidir. Endirim yoxlaması məhz bu
    ayrımın üstündə qurulur.
    """
    store_id, product_id = store_and_product
    with db_cursor() as cur:
        _insert(cur, product_id, store_id, 1.89, "site", "2026-09-08T09:00:00")
        _insert(cur, product_id, store_id, 1.49, "catalog", "2026-09-08T09:00:00")

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT source, price FROM price_snapshots WHERE product_id = ? "
            "ORDER BY source",
            (product_id,),
        ).fetchall()
    finally:
        conn.close()
    assert [(r["source"], r["price"]) for r in rows] == [
        ("catalog", 1.49),
        ("site", 1.89),
    ]


def test_ferqli_market_eyni_gunde_toqqusmur(store_and_product):
    store_id, product_id = store_and_product
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO stores (slug, name) VALUES (?, 'İkinci')",
            (f"t-snap-other-{uuid.uuid4().hex[:8]}",),
        )
        other_store = cur.lastrowid
        _insert(cur, product_id, store_id, 1.89, "site", "2026-09-08T09:00:00")
        _insert(cur, product_id, other_store, 2.05, "site", "2026-09-08T09:00:00")

    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) c FROM price_snapshots WHERE product_id = ?",
            (product_id,),
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count == 2


# ------------------------------------------------------------- sahə qaydaları


def test_nameluм_source_qebul_edilmir(store_and_product):
    """
    `source` yalnız 'site' və ya 'catalog' ola bilər.

    Səbəb: endirim yoxlaması `source='site'` süzgəci ilə işləyir. Üçüncü bir
    dəyər səssizcə yazılsa, həmin sətirlər yoxlamadan kənarda qalar və heç kim
    bunu görməz.
    """
    store_id, product_id = store_and_product
    with pytest.raises(sqlite3.IntegrityError):
        with db_cursor() as cur:
            _insert(cur, product_id, store_id, 1.89, "təxmin", "2026-09-08")


def test_is_promo_defolt_sifirdir(store_and_product):
    store_id, product_id = store_and_product
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO price_snapshots (product_id, store_id, price, source, observed_at) "
            "VALUES (?, ?, ?, 'site', '2026-09-08')",
            (product_id, store_id, 1.89),
        )
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT is_promo FROM price_snapshots WHERE product_id = ?", (product_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row["is_promo"] == 0


def test_qiymet_mecburidir(store_and_product):
    """Bilinməyən qiymət `None` yazılmır - sətir ümumiyyətlə yaranmır."""
    store_id, product_id = store_and_product
    with pytest.raises(sqlite3.IntegrityError):
        with db_cursor() as cur:
            cur.execute(
                "INSERT INTO price_snapshots "
                "(product_id, store_id, price, source, observed_at) "
                "VALUES (?, ?, NULL, 'site', '2026-09-08')",
                (product_id, store_id),
            )


# ------------------------------------------------------------- market birləşdirmə


def test_dublikat_market_birlesdirilir_data_itmir(temiz_araz):
    """
    `araz-market` sətrindəki hər şey `araz`-a köçür, sonra dublikat silinir.

    Bu, real bazada olan haldır: 183 qiymət "Araz Market"-də, 8 qiymət
    "Araz"-da idi və UI-da iki ayrı sütun görünürdü.
    """
    with db_cursor() as cur:
        cur.execute("INSERT INTO stores (slug, name) VALUES ('araz', 'Araz')")
        keep_id = cur.lastrowid
        cur.execute(
            "INSERT INTO stores (slug, name) VALUES ('araz-market', 'Araz Market')"
        )
        dup_id = cur.lastrowid
        tag = uuid.uuid4().hex[:8]
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key) VALUES (?, 'Süd', ?)",
            (f"m|sud|{tag}", f"m|sud|{tag}"),
        )
        product_id = cur.lastrowid
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path) "
            "VALUES (?, 'hash-merge-' || ?, 'x.pdf')",
            (dup_id, uuid.uuid4().hex[:8]),
        )
        catalog_id = cur.lastrowid
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price) "
            "VALUES (?, ?, ?, 1.89)",
            (product_id, dup_id, catalog_id),
        )
        _insert(cur, product_id, dup_id, 1.89, "site", "2026-09-08")

    conn = get_connection()
    try:
        applied = _merge_duplicate_stores(conn)
        conn.commit()

        assert applied, "birləşdirmə tətbiq olunmalı idi"
        assert (
            conn.execute(
                "SELECT COUNT(*) c FROM stores WHERE slug = 'araz-market'"
            ).fetchone()["c"]
            == 0
        ), "dublikat market sətri silinməli idi"

        for table in ("prices", "catalogs", "price_snapshots"):
            moved = conn.execute(
                f"SELECT COUNT(*) c FROM {table} WHERE store_id = ?", (keep_id,)
            ).fetchone()["c"]
            assert moved == 1, f"{table} sətri köçürülmədi"

        assert (
            conn.execute(
                "SELECT name FROM stores WHERE id = ?", (keep_id,)
            ).fetchone()["name"]
            == "Araz"
        )
    finally:
        conn.close()


def test_birlesdirme_tekrar_cagirilanda_sakit_kecir(temiz_araz):
    """Miqrasiya hər `init_db()` çağırışında işləyir - ikinci dəfə heç nə etməməlidir."""
    conn = get_connection()
    try:
        assert _merge_duplicate_stores(conn) == []
    finally:
        conn.close()


def test_hedef_yoxdursa_dublikat_adi_duzelir(temiz_araz):
    """
    Yalnız `araz-market` varsa, köçürüləcək yer yoxdur - adı düzəldilir.

    Bunsuz növbəti kataloq yükləməsi yenidən iki ayrı market yaradardı.
    """
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO stores (slug, name) VALUES ('araz-market', 'Araz Market')"
        )
        only_id = cur.lastrowid

    conn = get_connection()
    try:
        _merge_duplicate_stores(conn)
        conn.commit()
        row = conn.execute("SELECT slug, name FROM stores WHERE id = ?", (only_id,)).fetchone()
    finally:
        conn.close()
    assert (row["slug"], row["name"]) == ("araz", "Araz")


def test_init_db_tekrar_cagirila_biler():
    """Sxem + miqrasiya idempotentdir."""
    init_db()
    init_db()
    conn = get_connection()
    try:
        tables = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    finally:
        conn.close()
    assert "price_snapshots" in tables
