"""
Testlər üçün AYRICA verilənlər bazası.

NİYƏ BU FAYL YARANDI — REAL ZƏRƏRDƏN SONRA.
Əvvəl `conftest.py` yox idi və `pytest` birbaşa `data/basketiq.db` üzərində
işləyirdi — yəni istifadəçinin ÖZ bazası üzərində. `tests/test_mcp.py` və
`tests/test_voice.py` isə belə başlayır:

    DELETE FROM basket_items WHERE basket_id = 1
    INSERT INTO basket_items (basket_id, product_id, qty) VALUES (1, ?, ?)

`basket_id = 1` dashboard-un işlətdiyi səbətdir. Nəticə: hər `pytest`
qaçışı istifadəçinin səbətini silib öz test məhsulları ilə əvəz edirdi.
Səhv SƏSSİZ idi - testlər yaşıl keçirdi, sadəcə dashboard-a girəndə səbətdə
tanımadığın məhsullar görünürdü.

NECƏ HƏLL OLUNUR?
`DATABASE_PATH` mühit dəyişəni `app.config` idxal olunmamışdan ƏVVƏL müvəqqəti
fayla yönəldilir. `conftest.py` pytest tərəfindən test modullarından əvvəl
oxunur, ona görə bu, işləyən yeganə yerdir - fixture çox gec olardı.

BAZA HƏR SESSİYADA SIFIRDAN QURULUR. Testlər lazım olan datanı özləri yaradır;
"real bazada nə varsa ondan istifadə etmək" onsuz da səhv yanaşmadır - nəticə
maşından maşına dəyişər.
"""

import os
import tempfile
from pathlib import Path

import pytest

# DİQQƏT: bu sətirlər `app.config` idxalından ƏVVƏL işləməlidir.
# Ona görə burada, modul səviyyəsində dayanır - funksiyanın içində yox.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="basketiq-test-"))
os.environ["DATABASE_PATH"] = str(_TMP_DIR / "test.db")
os.environ.setdefault("DATA_DIR", str(_TMP_DIR))

from app.db import db_cursor, init_db  # noqa: E402  (yuxarıdakı env-dən sonra olmalıdır)


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """Sxemi qurur; sessiya bitəndə müvəqqəti qovluğu silir."""
    init_db()
    yield
    # Qovluğu silmək məcburi deyil (OS onsuz da təmizləyir), amma
    # təkrar qaçışlarda disk dolmasın.
    import shutil

    shutil.rmtree(_TMP_DIR, ignore_errors=True)


# --------------------------------------------------------------- test marketi


def make_store(slug: str, name: str) -> int:
    """
    Test üçün market yaradır (və ya mövcudunun id-sini qaytarır).

    NİYƏ ORTAQ KÖMƏKÇİ LAZIM OLDU?
    İstifadəçiyə görünən bütün hesablamalar artıq YALNIZ `app/stores.py`-dəki
    dörd marketi götürür (`store_filter`). Yəni test uydurma slug ilə market
    yaratsa - «t-bravo», «Analitika Test A» - həmin market cavaba ÜMUMİYYƏTLƏ
    düşmür və test səbəbi görünməyən şəkildə sınır.

    Ona görə testlər də REAL slug-larla işləməlidir: `araz`, `bravo`,
    `bazar-store`, `rahat`. Bu, testi məhsulun həqiqi qaydasına bağlayır.

    İKİ QAYDA:
      1. YARATMA İDEMPOTENTDİR - baza sessiyada bir dəfə qurulur və bir neçə
         test modulu eyni marketi yaratmaq istəyir; `slug` isə UNIQUE-dir.
      2. MARKET SƏTRİ TEARDOWN-DA SİLİNMİR - onu silsək, eyni marketi
         işlədən digər modul test SIRASINDAN asılı olaraq sınardı. Testlər
         öz qiymətlərini və məhsullarını silir, market sətri isə qalır
         (müvəqqəti bazadır, sessiya sonunda onsuz da yox olur).
    """
    from app.db import db_cursor

    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO stores (slug, name) VALUES (?, ?) ON CONFLICT(slug) DO NOTHING",
            (slug, name),
        )
        cur.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
        return cur.fetchone()["id"]


# ============================================================================
# PAYLAŞILAN SƏBƏT FIXTURE-LƏRİ
# ============================================================================
# `test_basket.py`-dan bura KÖÇÜRÜLDÜ: `test_basket_hero.py` da onları
# işlədir. Modullar arasında fixture idxal etmək pytest-də işləyir, amma
# ruff onu F811 kimi tutur (parametr adı idxal olunmuş adı örtür) - və
# haqlıdır: idxal edilən fixture həqiqətən qeyri-adi konstruksiyadır.
# `conftest.py` pytest-in bunun üçün nəzərdə tutduğu yerdir.

@pytest.fixture
def empty_basket():
    """Hər test öz səbəti ilə işləsin - ümumi səbətin vəziyyətindən asılı olmasın."""
    with db_cursor() as cur:
        cur.execute("INSERT INTO baskets (name) VALUES ('test')")
        basket_id = cur.lastrowid
    yield basket_id
    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE basket_id = ?", (basket_id,))
        cur.execute("DELETE FROM baskets WHERE id = ?", (basket_id,))


@pytest.fixture
def sample_data():
    """
    İki market, üç məhsul:
      - süd    : hər iki marketdə (Bravo ucuz)
      - düyü   : hər iki marketdə (Araz ucuz)
      - çay    : yalnız Araz-da
    Süd iki ayrı product sətridir, amma eyni group_key altındadır -
    yəni matching işləmiş kimi.
    """
    created = {"stores": [], "products": [], "catalogs": []}

    # REAL market slug-ları işlədilir. Müqayisə yalnız `app/stores.py`
    # reyestrindəki dörd marketi götürdüyü üçün uydurma slug ilə yaradılmış
    # market cavaba ÜMUMİYYƏTLƏ düşmür - test isə səbəbi görünməyən şəkildə
    # sınardı. Təfərrüat: `conftest.make_store`.
    for slug, name in [("bravo", "Bravo"), ("araz", "Araz")]:
        created["stores"].append(make_store(slug, name))

    with db_cursor() as cur:
        for i, store_id in enumerate(created["stores"]):
            cur.execute(
                "INSERT INTO catalogs (store_id, file_hash, file_path, source_type) "
                "VALUES (?, ?, ?, 'image')",
                (store_id, f"testhash{i}", f"data/raw/test{i}.png"),
            )
            created["catalogs"].append(cur.lastrowid)

        # (canonical_key, group_key, ad)
        rows = [
            ("t|sud|bravo|1l", "t|sud|1l", "süd"),      # eyni qrup
            ("t|sud|araz|1l", "t|sud|1l", "süd"),       # eyni qrup
            ("t|duyu|1kg", "t|duyu|1kg", "düyü"),
            ("t|cay|250g", "t|cay|250g", "çay"),
        ]
        for key, group, name in rows:
            cur.execute(
                "INSERT INTO products (canonical_key, name, brand, size_value, size_unit, "
                "                      category, group_key) VALUES (?, ?, NULL, 1, 'l', 'digər', ?)",
                (key, name, group),
            )
            created["products"].append(cur.lastrowid)

    sud_bravo, sud_araz, duyu, cay = created["products"]
    bravo, araz = created["stores"]
    cat_bravo, cat_araz = created["catalogs"]

    with db_cursor() as cur:
        prices = [
            (sud_bravo, bravo, cat_bravo, 1.89),
            (sud_araz, araz, cat_araz, 2.05),
            (duyu, bravo, cat_bravo, 3.40),
            (duyu, araz, cat_araz, 3.15),
            (cay, araz, cat_araz, 3.80),
        ]
        for product_id, store_id, catalog_id, price in prices:
            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price, unit_price) "
                "VALUES (?, ?, ?, ?, ?)",
                (product_id, store_id, catalog_id, price, price),
            )

    yield {"stores": created["stores"], "sud": sud_bravo, "duyu": duyu, "cay": cay}

    # Təmizlik: test datası real DB-də qalmasın
    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE product_id IN "
                    "(SELECT id FROM products WHERE canonical_key LIKE 't|%')")
        cur.execute("DELETE FROM prices WHERE catalog_id IN "
                    f"({','.join('?' * len(created['catalogs']))})", created["catalogs"])
        cur.execute("DELETE FROM catalogs WHERE id IN "
                    f"({','.join('?' * len(created['catalogs']))})", created["catalogs"])
        cur.execute("DELETE FROM products WHERE canonical_key LIKE 't|%'")
        # MARKET SƏTRİ SİLİNMİR: `araz`/`bravo` reyestr marketləridir və digər
        # test modulları da onları işlədir. Silsək, testlərin SIRASI nəticəyə
        # təsir edərdi. Baza onsuz da müvəqqətidir (bax `conftest.py`).
