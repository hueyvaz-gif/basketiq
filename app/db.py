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


def _migrate(conn: sqlite3.Connection) -> None:
    """
    Köhnə DB-lərə yeni sütunları əlavə edir.

    Niyə? Sən artıq kataloq yükləmisən - DB-ni silmək o datanı da silərdi.
    Kiçik layihədə tam miqrasiya sistemi (Alembic) artıqdır; bu, kifayətdir.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(products)")}
    if "group_key" not in columns:
        conn.execute("ALTER TABLE products ADD COLUMN group_key TEXT")

    # Sütun mövcud olduqdan SONRA indeks
    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_group ON products(group_key)")

    # group_key boş qalan sətirlər öz canonical_key-ini alır
    conn.execute(
        "UPDATE products SET group_key = canonical_key "
        "WHERE group_key IS NULL OR group_key = ''"
    )


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


def db_stats() -> dict:
    """/health üçün sadə sayğaclar."""
    conn = get_connection()
    try:
        out = {}
        for table in ("stores", "catalogs", "products", "prices"):
            out[table] = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
        return out
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"DB hazırdır: {settings.db_path}")
    print(db_stats())
