"""
SQLite bağlantısı və cədvəl sxemi.

Niyə sqlite3 (ORM yox)? Layihədə cəmi 6 cədvəl var, sorğular sadədir.
SQLAlchemy əlavə etsək, layihəyə öyrənmə dəyəri qatmayan bir qat gələr.
"""

import sqlite3
from contextlib import contextmanager

from app.config import settings

SCHEMA = """
PRAGMA foreign_keys = ON;

-- Marketlər
CREATE TABLE IF NOT EXISTS stores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,      -- 'market-a'
    name        TEXT NOT NULL,
    website     TEXT
);

-- Yüklənmiş kataloq faylları. file_hash = eyni kataloqu 2 dəfə emal etməmək üçün.
CREATE TABLE IF NOT EXISTS catalogs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id    INTEGER NOT NULL REFERENCES stores(id),
    file_hash   TEXT NOT NULL UNIQUE,
    file_path   TEXT NOT NULL,
    source_url  TEXT,
    source_type TEXT,                      -- 'pdf_text' | 'pdf_scan' | 'image'
    valid_from  TEXT,
    valid_to    TEXT,
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now')),
    status      TEXT NOT NULL DEFAULT 'new' -- new | parsed | failed | skipped
);

-- Unikal məhsul. canonical_key fərqli marketlərdəki eyni məhsulu birləşdirir.
CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key TEXT NOT NULL UNIQUE,    -- 'milla|sud|1l'
    name          TEXT NOT NULL,
    brand         TEXT,
    size_value    REAL,
    size_unit     TEXT,                    -- kg | g | l | ml | pcs
    category      TEXT,
    -- Fərqli marketlərdə eyni sayılan məhsullar eyni group_key alır.
    -- Başlanğıcda group_key = canonical_key; matching işlədikdən sonra birləşir.
    group_key     TEXT
);
-- QEYD: group_key üzrə indeks burada YARADILMIR.
-- Səbəb: köhnə DB-də "CREATE TABLE IF NOT EXISTS" cədvəli dəyişmir, sütun isə
-- yalnız _migrate() içində əlavə olunur. İndeksi burada yazsaq, o, hələ mövcud
-- olmayan sütuna istinad edib xəta verər. Ona görə indeks _migrate()-dədir.

-- Qiymət müşahidəsi. unit_price = 1 kq / 1 L qiyməti -> bütün müqayisə bunun üstündədir.
CREATE TABLE IF NOT EXISTS prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    store_id    INTEGER NOT NULL REFERENCES stores(id),
    catalog_id  INTEGER NOT NULL REFERENCES catalogs(id),
    price       REAL NOT NULL,
    old_price   REAL,
    unit_price  REAL,
    raw_line    TEXT,                      -- OCR-dən gələn orijinal sətir (şəffaflıq üçün)
    seen_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_prices_product ON prices(product_id);
CREATE INDEX IF NOT EXISTS idx_prices_store   ON prices(store_id);
CREATE INDEX IF NOT EXISTS idx_prices_seen    ON prices(seen_at);

-- Gündəlik qiymət müşahidəsi (BasketIQ v2).
--
-- NİYƏ `prices` KİFAYƏT ETMİR? `prices` bir KATALOQ sətrinə bağlıdır
-- (`catalog_id` NOT NULL) - yəni yalnız həftəlik jurnaldan gələn qiyməti
-- saxlaya bilir. Onlayn mağazadan gündəlik çəkilən qiymətin kataloqu yoxdur.
--
-- `source` sahəsi həlledicidir: sayt qiyməti ilə kataloq iddiası EYNİ
-- cədvəldədir, amma bir-birinə qarışmır. Endirim yoxlaması yalnız
-- `source='site'` sətirlərini oxuyur - kataloqun öz iddiasını yenə kataloqla
-- təsdiqləmək dairəvi məntiqdir.
--
-- Sətirlər ÜSTÜNƏ YAZILMIR: hər gün yeni sətir. Tarixçə qrafiki və endirim
-- yoxlaması bunun üzərində qurulur.
CREATE TABLE IF NOT EXISTS price_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id   INTEGER NOT NULL REFERENCES products(id),
    store_id     INTEGER NOT NULL REFERENCES stores(id),
    price        REAL    NOT NULL,
    old_price    REAL,                    -- endirimdən əvvəlki qiymət (varsa)
    unit_price   REAL,                    -- 1 kq / 1 L üzrə
    is_promo     INTEGER NOT NULL DEFAULT 0,
    source       TEXT    NOT NULL CHECK (source IN ('site', 'catalog')),
    observed_at  TEXT    NOT NULL         -- ISO tarix və ya tam vaxt möhürü
);

CREATE INDEX IF NOT EXISTS ix_snapshots_product_date
    ON price_snapshots(product_id, observed_at);

-- GÜNDƏ BİR SƏTİR - və məhz gündə.
--
-- Tapşırıqdakı ilkin variant sütunun özünə idi:
--     UNIQUE(product_id, store_id, source, observed_at)
-- `observed_at` tam vaxt möhürü saxladığı üçün bu indeks HEÇ NƏYİ tutmurdu:
-- eyni məhsul saat 09:00 və 18:30-da çəkiləndə iki ayrı sətir yaranırdı,
-- yəni "hər gün bir sətir" qaydası kağız üzərində qalırdı. Ölçüldü:
-- ifadəli indekslə ikinci yazı IntegrityError verir, ertəsi gün isə keçir.
CREATE UNIQUE INDEX IF NOT EXISTS ux_snapshot_daily
    ON price_snapshots(product_id, store_id, source, date(observed_at));

-- MƏNBƏ YOXLAMASININ GÜNDƏLİK QEYDİ
--
-- NİYƏ LAZIMDIR? Üç marketin mənbəyi ölçülmüş səbəblərlə bağlıdır
-- (`ingestion/profiles.py`). Bazar Store-un saytı «yenilənmə işləri»
-- elanındadır və nə vaxt qayıdacağı bilinmir. Əl ilə yoxlamaq unudulur:
-- sayt qayıdar, biz isə aylarla «mənbə yoxdur» yazmağa davam edərik.
--
-- CƏDVƏL TARİXÇƏDİR, BAYRAQ DEYİL. Yalnız «indi işləyir/işləmir» saxlasaq,
-- «nə vaxtdan bəri bağlıdır?» və «keçən həftə bir gün açıq idimi?»
-- suallarına cavab olmazdı. Sətir üstünə yazılmır - hər gün yeni sətir.
--
-- GÜNDƏ BİR SƏTİR: `price_snapshots`-dakı ilə eyni qayda və eyni səbəb -
-- ifadəli unikal indeks. Gün ərzində təkrar yoxlama xəta vermir, həmin
-- günün sətrini yeniləyir.
CREATE TABLE IF NOT EXISTS source_probes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT    NOT NULL,
    alive       INTEGER NOT NULL DEFAULT 0,   -- səhifədə real məzmun varmı?
    http_status INTEGER,
    text_length INTEGER,                      -- görünən mətnin uzunluğu
    catalog_links INTEGER NOT NULL DEFAULT 0, -- tapılan PDF/şəkil linki
    note        TEXT,                         -- nə görüldü (insan üçün)
    checked_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_probe_daily
    ON source_probes(slug, date(checked_at));

-- İstifadəçinin səbəti
CREATE TABLE IF NOT EXISTS baskets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL DEFAULT 'Mənim səbətim',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- İstifadəçi profili: tövsiyəni şəxsiləşdirən parametrlər.
-- Tək sətir (id=1) - layihədə istifadəçi hesabı yoxdur. Çox istifadəçi lazım
-- olsa, user_id sütunu əlavə etmək kifayətdir.
CREATE TABLE IF NOT EXISTS profile (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    household_size    INTEGER NOT NULL DEFAULT 1,
    weekly_budget     REAL,                          -- NULL = büdcə limiti yoxdur
    max_stores        INTEGER NOT NULL DEFAULT 1,    -- neçə markete getməyə hazırdır
    min_split_saving  REAL NOT NULL DEFAULT 1.0,     -- 2-ci market bundan az qənaətə dəyməz
    prefer_unit_price INTEGER NOT NULL DEFAULT 1,    -- kq/litr qiymətinə baxsınmı
    avoid             TEXT NOT NULL DEFAULT ''       -- vergüllə ayrılmış açar sözlər
);

CREATE TABLE IF NOT EXISTS basket_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    basket_id  INTEGER NOT NULL REFERENCES baskets(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty        REAL NOT NULL DEFAULT 1,
    UNIQUE(basket_id, product_id)
);

-- MƏHSUL ŞƏKİLLƏRİ (M3) — marketin öz saytından çəkilmiş foto.
--
-- NİYƏ AYRICA CƏDVƏL, `products.image_path` DEYİL? Çünki burada saxlanılan
-- şey yalnız fayl adı deyil: hansı ünvandan gəldiyi, uyğunluğun etibarı,
-- nə vaxt çəkildiyi və neçə cəhd edildiyi də lazımdır. Bunlar olmadan
-- «bu şəkil niyə bu məhsuldadır?» sualına cavab vermək mümkün olmazdı.
--
-- `source_url` VƏ `fetched_at` MƏCBURİDİR: şəkil kənar saytdan gəlir və
-- marketlərin şərtləri dəyişə bilər - mənbəyə istinad saxlanılmalıdır.
--
-- `status`: ok | rejected | failed
--   ok        şəkil var və göstərilir
--   rejected  uyğunluq zəif idi - AVTOMATİK təkrar sınanmır (manual siyahı)
--   failed    sayt cavab vermədi - həftədə bir təkrar sınanır
--
-- `manual` = 1 olan sətrin üstündən avtomatika YAZMIR (3.6): insan qərarı
-- maşın qərarından üstündür.
CREATE TABLE IF NOT EXISTS product_images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL UNIQUE REFERENCES products(id),
    image_path  TEXT,
    source_url  TEXT,
    confidence  REAL,
    image_hash  TEXT,
    width       INTEGER,                    -- `<img width>`: sıçrayışın qarşısını alır
    height      INTEGER,
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now')),
    status      TEXT NOT NULL DEFAULT 'ok',
    attempts    INTEGER NOT NULL DEFAULT 0,
    manual      INTEGER NOT NULL DEFAULT 0,
    note        TEXT
);

CREATE INDEX IF NOT EXISTS idx_product_images_status ON product_images(status);
CREATE INDEX IF NOT EXISTS idx_product_images_hash ON product_images(image_hash);

-- REKLAM SİFARİŞLƏRİ (E21).
--
-- NİYƏ AYRICA CƏDVƏL, KONFİQ FAYLI YOX? Reklam vaxt üzrə dəyişir (başlanğıc
-- və bitmə tarixi var), sayılır (göstərim/klik) və admin panelindən idarə
-- olunur. Konfiq faylı bunların heç birini verə bilmir.
--
-- SLOT NƏDİR? Səhifədəki yer: 'home-banner' (market şəbəkəsi ilə endirimlər
-- arasında). Slot adı KODDA sabitdir (`app/ads.py:SLOTS`) - bazadan gələn
-- sərbəst mətn səhifədə yer aça bilməz.
--
-- SAYĞACLAR SƏTRİN ÖZÜNDƏDİR: ayrı hadisə cədvəli daha dəqiq olardı, amma bu
-- layihədə reklam sayı bir neçədir və hesabat «neçə göstərim, neçə klik»
-- sualından ibarətdir. Ayrı cədvəl cavabı dəyişmədən mürəkkəblik gətirərdi.
CREATE TABLE IF NOT EXISTS ads (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    advertiser   TEXT NOT NULL,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',
    image_path   TEXT,                          -- /static/images/ads/... (NULL = mətn reklamı)
    target_url   TEXT NOT NULL,
    slot         TEXT NOT NULL,                 -- app/ads.py:SLOTS
    starts_at    TEXT NOT NULL,                 -- YYYY-MM-DD
    ends_at      TEXT NOT NULL,                 -- YYYY-MM-DD (daxil)
    active       INTEGER NOT NULL DEFAULT 1,
    impressions  INTEGER NOT NULL DEFAULT 0,
    clicks       INTEGER NOT NULL DEFAULT 0,
    is_sample    INTEGER NOT NULL DEFAULT 0,    -- nümunə sifariş: real satış deyil
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ads_slot ON ads(slot, active);
"""


# İKİ QİYMƏT QATININ ORTAQ GÖRÜNÜŞÜ
# =================================
# Layihədə qiymət İKİ cədvəldədir və bu, qəsdəndir:
#
#   `prices`          kataloq İDDİASI  - «9.99 → 5.99», `catalog_id` NOT NULL
#   `price_snapshots` rəf QİYMƏTİ      - onlayn mağazadan, `source='site'`
#
# Amma «bu marketdə neçə məhsul var?» sualı üçün fərq YOXDUR: hər ikisi
# həmin marketdə tapılmış məhsuldur. Sayğac yalnız `prices`-i oxusaydı,
# kataloqu olmayan market (Bravo) həmişə «0 məhsul» görünərdi - halbuki
# minlərlə rəf qiyməti var.
#
# NİYƏ SABİT, NİYƏ VIEW DEYİL? `CREATE VIEW` sxem miqrasiyası tələb edir və
# köhnə bazalarda `init_db()`-dən əvvəl işləyən sorğu onu tapmazdı. Sabit
# CTE hər sorğuya öz daxilində qoşulur - miqrasiya lazım deyil.
#
# `layer` sütunu mənşəyi saxlayır: UI «neçəsi rəfdən, neçəsi kataloqdan»
# sualına cavab verə bilsin.
#
# `row_id` SIRALAMA ÜÇÜNDÜR və vacibdir. Eyni kataloqdan gələn sətirlərin
# `seen_at`-i EYNİDİR (hamısı bir emalda yazılır), ona görə «sonuncu sətir»
# qaydası yalnız `at`-a görə sıralananda QEYRİ-MÜƏYYƏN olur - SQLite hər
# dəfə fərqli sətir qaytara bilər. Ölçüldü: bir məhsulun kartında qiymət
# 2.35 ilə 2.99 arasında dəyişirdi. Sıralama HƏMİŞƏ `at, layer, row_id`
# olmalıdır (`layer` iki cədvəlin id-ləri üst-üstə düşdüyü üçün lazımdır).
# `old_price` HƏR İKİ QATDA VAR (2026-09-10-dan). Əvvəl `price_snapshots`
# yalnız `is_promo` bayrağını saxlayırdı və sayt sətrində köhnə qiymət NULL
# qalırdı - nəticədə mağaza qatının endirimləri faizi hesablana bilmirdi və
# «bugünün endirimləri» siyahısı yalnız kataloq qatından ibarət görünürdü.
PRICE_ROWS_CTE = """
WITH price_rows AS (
    SELECT id AS row_id, product_id, store_id, catalog_id, price, old_price, unit_price,
           flags, seen_at AS at, 'catalog' AS layer
      FROM prices
    UNION ALL
    -- `flags` YALNIZ KATALOQ QATINDADIR: sağlamlıq yoxlaması OCR sətrinə
    -- baxır, mağaza qatında isə OCR yoxdur (data strukturludur). Sayt
    -- sətrində NULL qalır - yəni karantin şərti onu atmır.
    SELECT id AS row_id, product_id, store_id, NULL AS catalog_id, price, old_price, unit_price,
           NULL AS flags, observed_at AS at, 'site' AS layer
      FROM price_snapshots
     WHERE source = 'site'
)
"""


def get_connection() -> sqlite3.Connection:
    """Yeni bağlantı qaytarır. Sətirlər dict kimi oxunur (row['name'])."""
    settings.ensure_dirs()
    conn = sqlite3.connect(settings.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor():
    """with db_cursor() as cur: ... -> uğurlu olsa commit, xəta olsa rollback."""
    conn = get_connection()
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Eyni marketin iki ayrı sətir kimi yazıldığı hallar.
#
# `(mənbə slug, hədəf slug, düzgün ad)` - mənbədəki bütün sətirlər hədəfə
# köçürülür, sonra mənbə sətri silinir.
#
# NİYƏ LAZIM OLDU? Kataloq yüklənəndə market adı sərbəst mətndir və
# `get_or_create_store()` onu SLUG üzrə axtarır. "Araz" əl ilə, "Araz Market"
# isə scraper tərəfindən yaradılmışdı - eyni şirkət, iki market. Nəticə
# istifadəçi panelində görünürdü: müqayisə cədvəlində iki ayrı sütun və
# "Araz Market səbətdəki məhsulları satmır" yazısı.
#
# Bu siyahı ƏL İLƏ doldurulur. Adları avtomatik oxşarlığa görə birləşdirmək
# təhlükəlidir: "Bravo" ilə "Bravo Express" fərqli şəbəkə ola bilər.
STORE_MERGES: tuple[tuple[str, str, str], ...] = (
    ("araz-market", "araz", "Araz"),
    # Eyni tələ ikinci dəfə: mağaza qatı «Bravo Market» adı ilə çağırdı və
    # `bravo-market` slug-u yarandı, halbuki mövcud sətir `bravo`-dur.
    # Kök səbəb `app/api/shop.py:resolve_store_id()`-də bağlandı; bu sətir
    # artıq yaranmış datanı birləşdirir.
    ("bravo-market", "bravo", "Bravo"),
)


def _merge_duplicate_stores(conn: sqlite3.Connection) -> list[str]:
    """
    `STORE_MERGES` siyahısını tətbiq edir. Təkrar çağırmaq təhlükəsizdir.

    Data İTMİR: qiymətlər, kataloqlar və snapshot-lar hədəf marketə köçürülür,
    yalnız artıq boşalmış `stores` sətri silinir.
    """
    applied: list[str] = []
    for src_slug, dst_slug, canonical_name in STORE_MERGES:
        src = conn.execute("SELECT id FROM stores WHERE slug = ?", (src_slug,)).fetchone()
        if src is None:
            continue

        dst = conn.execute("SELECT id FROM stores WHERE slug = ?", (dst_slug,)).fetchone()
        if dst is None:
            # Hədəf yoxdur - köçürəcək yer də yoxdur. Sadəcə adını düzəldirik,
            # beləliklə növbəti dəfə təkrar yaranmır.
            conn.execute(
                "UPDATE stores SET slug = ?, name = ? WHERE id = ?",
                (dst_slug, canonical_name, src["id"]),
            )
            applied.append(f"{src_slug} → {dst_slug} (adı dəyişdirildi)")
            continue

        if src["id"] == dst["id"]:
            continue

        moved = 0
        for table in ("prices", "catalogs", "price_snapshots"):
            cur = conn.execute(
                f"UPDATE {table} SET store_id = ? WHERE store_id = ?",
                (dst["id"], src["id"]),
            )
            moved += cur.rowcount
        conn.execute("DELETE FROM stores WHERE id = ?", (src["id"],))
        conn.execute(
            "UPDATE stores SET name = ? WHERE id = ?", (canonical_name, dst["id"])
        )
        applied.append(f"{src_slug} → {dst_slug} ({moved} sətir köçürüldü)")

    return applied


def _migrate(conn: sqlite3.Connection) -> None:
    """
    Köhnə DB-lərə yeni sütunları əlavə edir.

    Niyə? Sən artıq kataloq yükləmisən - DB-ni silmək o datanı da silərdi.
    Kiçik layihədə tam miqrasiya sistemi (Alembic) artıqdır; bu, kifayətdir.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(products)")}
    if "group_key" not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN group_key TEXT")

    # `old_price` MAĞAZA QATINA DA LAZIMDIR (2026-09-10).
    #
    # Cədvəl yalnız `is_promo` bayrağını saxlayırdı - «endirimdədir» demək
    # olurdu, amma NEÇƏ FAİZ olduğunu yox. Nəticədə Bravonun 3 369 endirimli
    # məhsulu «bugünün endirimləri» siyahısına PRİNSİPCƏ düşə bilmirdi və
    # siyahı yalnız Arazdan ibarət görünürdü.
    #
    # Data ONSUZ DA VAR İDİ: Wolt kartından köhnə qiymət `parse_card()` ilə
    # çıxarılır (`ExtractedProduct.old_price`), sadəcə yazılmırdı.
    snapshot_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(price_snapshots)")
    }
    if snapshot_columns and "old_price" not in snapshot_columns:
        conn.execute("ALTER TABLE price_snapshots ADD COLUMN old_price REAL")

    # Onlayn mağazadan gələn əlavə sahələr (BasketIQ v2).
    # `barcode` matching üçün BİRİNCİ açardır: eyni barkod = eyni məhsul,
    # LLM-ə göndərmək lazım deyil. `product_url` isə şəffaflıq üçündür -
    # qiymətin hansı səhifədən götürüldüyü göstərilə bilsin.
    # `image_path` — məhsulun ŞƏKLİ (BasketIQ v3).
    #
    # NİYƏ URL YOX, YERLİ YOL? Marketlərin bir hissəsi xarici saytdan şəkil
    # göstərməyə (hotlink) icazə vermir - şəkil brauzerdə qırıq görünərdi və
    # səbəbi heç bir yerdə yazılmazdı. Ona görə şəkil bir dəfə endirilir
    # (və ya kataloqdan kəsilir), `app/static/images/products/` altında
    # saxlanılır, bazada isə yalnız fayl adı qalır.
    #
    # BOŞ QALA BİLƏR: şəkli tapılmayan məhsul üçün UI neytral placeholder
    # göstərir - səhifə sınmır.
    # `name_norm` — AXTARIŞ üçün normallaşdırılmış ad (M1).
    #
    # NİYƏ SÜTUN, HƏR SORĞUDA HESABLAMA YOX? Fold funksiyasını sorğu anında
    # tətbiq etsək, SQL hər sətri Python-a çıxarıb çevirməli olardı - indeks
    # işə düşməzdi və axtarış məhsul sayı ilə birlikdə yavaşlayardı. Sütun
    # bir dəfə yazılır, sorğu isə hazır dəyərin üstündə işləyir.
    #
    # İÇİNDƏ BREND DƏ VAR: istifadəçi «milla sud» yazanda həm brendi, həm adı
    # bir sətirdə axtarır. İki ayrı sütun olsaydı, çoxsözlü sorğunun VƏ
    # məntiqi iki sütun arasında paylanardı və «milla» ilə «sud» fərqli
    # sahələrə düşəndə uyğunluq itərdi.
    for column, ddl in (
        ("barcode", "ALTER TABLE products ADD COLUMN barcode TEXT"),
        ("product_url", "ALTER TABLE products ADD COLUMN product_url TEXT"),
        ("image_path", "ALTER TABLE products ADD COLUMN image_path TEXT"),
        ("name_norm", "ALTER TABLE products ADD COLUMN name_norm TEXT"),
        # `match_key` — UYĞUNLAŞDIRMA açarı (`ingestion/normalize.py:match_key`).
        # canonical_key-in yanında AYRICA saxlanılır: canonical_key UNIQUE-dir
        # və mağaza çəkilişi məhsulu onunla tapır, ona görə dəyişdirilə bilməz.
        # Geri qaytarmaq üçün sütunu nəzərə almamaq kifayətdir — heç bir köhnə
        # sorğu onu oxumur.
        ("match_key", "ALTER TABLE products ADD COLUMN match_key TEXT"),
    ):
        if column not in columns:
            conn.execute(ddl)

    # --- prices.flags: sağlamlıq yoxlamasının nəticəsi (C12) ---
    #
    # Şübhəli sətir SİLİNMİR, nişanlanır: silinsəydi səhvi araşdırmaq mümkün
    # olmazdı. Sütun JSON siyahı saxlayır (`["deepDiscount"]`); boş və ya NULL
    # = sətir təmizdir. Bayraqların mənası `ingestion/quality.py`-dədir.
    price_columns = {r[1] for r in conn.execute("PRAGMA table_info(prices)")}
    if "flags" not in price_columns:
        conn.execute("ALTER TABLE prices ADD COLUMN flags TEXT")

    # --- product_images.width/height: `<img>` teqinin ölçü atributları (M3) ---
    #
    # ŞƏKLİN ÖLÇÜSÜ BAZADA SAXLANILIR ki, HTML qurulanda `width`/`height`
    # yazıla bilsin. Atributsuz brauzer yeri fayl gələnə qədər boş saxlayır
    # və sonra səhifə sıçrayır. Ölçünü diskdən oxumaq hər sorğuda fayl
    # açmaq demək olardı - bir dəfə endirmə anında bilinən dəyəri yazmaq
    # ucuzdur.
    image_columns = {r[1] for r in conn.execute("PRAGMA table_info(product_images)")}
    for column, ddl in (
        ("width", "ALTER TABLE product_images ADD COLUMN width INTEGER"),
        ("height", "ALTER TABLE product_images ADD COLUMN height INTEGER"),
    ):
        if column not in image_columns:
            conn.execute(ddl)

    # Sütun mövcud olduqdan SONRA indeks
    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_group ON products(group_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_name_norm ON products(name_norm)")

    # KÖHNƏ SƏTİRLƏR DOLDURULUR. Sütun boş qalsa, axtarış həmin məhsulları
    # HEÇ VAXT tapmazdı - və səhv səssiz olardı: sorğu işləyir, sadəcə nəticə
    # az gəlir. Yalnız `NULL` olanlar yazılır, yəni təkrar çağırış ucuzdur.
    from app.search_norm import fold  # dövri idxaldan qaçmaq üçün burada

    boşlar = conn.execute(
        "SELECT id, name, brand FROM products WHERE name_norm IS NULL"
    ).fetchall()
    for row in boşlar:
        conn.execute(
            "UPDATE products SET name_norm = ? WHERE id = ?",
            (fold(f"{row['brand'] or ''} {row['name'] or ''}".strip()), row["id"]),
        )
    # Barkod UNİKAL DEYİL: eyni barkod fərqli marketlərdə ayrı `products`
    # sətri kimi görünə bilər - onları birləşdirmək matching-in işidir,
    # bazanın deyil. İndeks yalnız axtarışı sürətləndirir.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")

    # match_key: `name_norm` ilə eyni qayda — yalnız NULL olanlar doldurulur.
    # Yeni çəkilişdən gələn sətirlər növbəti başlanğıcda və ya uyğunlaşdırma
    # işləyəndə (o, açarları özü yeniləyir) dolur.
    from ingestion.normalize import match_key  # dövri idxaldan qaçmaq üçün burada

    for row in conn.execute(
        "SELECT id, name, brand, size_value, size_unit FROM products WHERE match_key IS NULL"
    ).fetchall():
        conn.execute(
            "UPDATE products SET match_key = ? WHERE id = ?",
            (
                match_key(row["name"], row["brand"], row["size_value"], row["size_unit"]),
                row["id"],
            ),
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_match_key ON products(match_key)")

    # group_key boş qalan sətirlər öz canonical_key-ini alır
    conn.execute(
        "UPDATE products SET group_key = canonical_key "
        "WHERE group_key IS NULL OR group_key = ''"
    )

    _merge_duplicate_stores(conn)


def init_db() -> None:
    """Cədvəlləri yaradır və başlanğıc datanı əlavə edir. Təkrar çağırmaq təhlükəsizdir."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        # Ən azı bir səbət həmişə olsun ki, UI boş qalmasın
        conn.execute(
            "INSERT INTO baskets (id, name) SELECT 1, 'Mənim səbətim' "
            "WHERE NOT EXISTS (SELECT 1 FROM baskets WHERE id = 1)"
        )
        # Profil də həmişə mövcud olsun - UI boş cavabla qarşılaşmasın
        conn.execute(
            "INSERT INTO profile (id) SELECT 1 "
            "WHERE NOT EXISTS (SELECT 1 FROM profile WHERE id = 1)"
        )
        conn.commit()
    finally:
        conn.close()

    # NÜMUNƏ REKLAM (E24): slot canlı nümunə ilə gəlir. İdempotentdir və
    # yalnız baza tamam boş olanda işə düşür - admin nümunəni silsə, o,
    # növbəti başlanğıcda geri qayıtmır. İdxal BURADA edilir, çünki
    # `app/ads.py` öz növbəsində `app/db.py`-dan asılıdır.
    from app.ads import seed_sample_ad

    seed_sample_ad()


def db_stats() -> dict:
    """/health üçün sadə sayğaclar."""
    conn = get_connection()
    try:
        out = {}
        for table in ("stores", "catalogs", "products", "prices", "price_snapshots"):
            out[table] = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
        return out
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"DB hazırdır: {settings.db_path}")
    print(db_stats())
