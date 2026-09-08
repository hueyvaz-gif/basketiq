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

from app.db import init_db  # noqa: E402  (yuxarıdakı env-dən sonra olmalıdır)


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
