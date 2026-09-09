"""
Yetim (qiymətsiz) məhsulların silinməsi.

REAL VƏZİYYƏTDƏN ÇIXIB: 137-ci kataloq yenidən emal olunandan sonra bazada
214 məhsuldan 140-ı qiymətsiz qalmışdı. `save_products()` kataloqun qiymət
sətirlərini silib yenidən yazır, `products` cədvəlinə isə toxunmur - ona görə
əvvəlki emalın məhsulu bazada ilişib qalır.

Testin əsas sualı: silmə YALNIZ qiymətsiz məhsula toxunurmu? Qiyməti olan
məhsulu silmək datanı itirmək deməkdir və geri qaytarmaq üçün yalnız ehtiyat
nüsxə qalır.
"""

import uuid

import pytest

from app.db import db_cursor, get_connection, init_db
from tools.purge_orphans import purge


@pytest.fixture(autouse=True)
def _db():
    init_db()


def _yarat(name: str, with_price: bool, image: str | None = None) -> int:
    """Bir məhsul yaradır; `with_price` isə ona bir qiymət sətri də yazır."""
    key = f"{name}-{uuid.uuid4().hex[:8]}"
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key, image_path) "
            "VALUES (?, ?, ?, ?)",
            (key, name, key, image),
        )
        product_id = cur.lastrowid
        if with_price:
            cur.execute(
                "INSERT INTO stores (name, slug) VALUES (?, ?)",
                (f"Market {key}", f"m-{key}"),
            )
            store_id = cur.lastrowid
            cur.execute(
                "INSERT INTO catalogs (store_id, file_hash, file_path, source_type, status) "
                "VALUES (?, ?, ?, 'image', 'extracted')",
                (store_id, key, f"data/raw/{key}.png"),
            )
            catalog_id = cur.lastrowid
            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price) "
                "VALUES (?, ?, ?, ?)",
                (product_id, store_id, catalog_id, 1.99),
            )
    return product_id


def _var(product_id: int) -> bool:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT 1 FROM products WHERE id = ?", (product_id,)
        ).fetchone() is not None
    finally:
        conn.close()


def test_yalniz_qiymetsiz_mehsul_silinir():
    yetim = _yarat("yetim düşbərə", with_price=False)
    diri = _yarat("qiymətli düşbərə", with_price=True)

    purge(apply=True)

    assert not _var(yetim), "qiymətsiz məhsul qalmamalıdır"
    assert _var(diri), "qiyməti olan məhsul SİLİNMƏMƏLİDİR"


def test_on_baxis_hec_ne_silmir():
    """`--apply` verilmədən silmə olmamalıdır - ön baxış zərərsizdir."""
    yetim = _yarat("ön baxış məhsulu", with_price=False)

    purge(apply=False)

    assert _var(yetim)


def test_sebet_setri_de_gedir(tmp_path):
    """
    Qiymətsiz məhsul səbətdə qalsa, istifadəçi onu nə görə, nə də silə bilir -
    səbətdə «qiyməti tapılmadı» sətri kimi ilişib qalır.
    """
    yetim = _yarat("səbətdəki yetim", with_price=False)
    with db_cursor() as cur:
        cur.execute("INSERT OR IGNORE INTO baskets (id, name) VALUES (1, 'test')")
        cur.execute(
            "INSERT INTO basket_items (basket_id, product_id, qty) VALUES (1, ?, 1)",
            (yetim,),
        )

    purge(apply=True)

    conn = get_connection()
    try:
        qaliq = conn.execute(
            "SELECT COUNT(*) FROM basket_items WHERE product_id = ?", (yetim,)
        ).fetchone()[0]
    finally:
        conn.close()
    assert qaliq == 0


def test_sekil_fayli_da_silinir(tmp_path, monkeypatch):
    """Sahibsiz qalan şəkil faylı diskdə qalmamalıdır."""
    import tools.purge_orphans as modul

    monkeypatch.setattr(modul, "PRODUCT_IMAGE_DIR", tmp_path)
    fayl = tmp_path / "p999999.jpg"
    fayl.write_bytes(b"saxta")
    _yarat("şəkilli yetim", with_price=False, image="p999999.jpg")

    purge(apply=True)

    assert not fayl.exists()
