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
