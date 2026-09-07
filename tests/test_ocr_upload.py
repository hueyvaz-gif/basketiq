"""
OCR + upload uçdan-uca testi.

Real kataloq faylı olmadan işləyir: PIL ilə süni "kataloq" şəkli çəkirik,
onu OCR-dən keçiririk və upload endpoint-inə göndəririk.

Niyə süni şəkil? Real kataloqu repo-ya qoymaq olmaz (müəllif hüququ), amma
pipeline-ın qırılmadığını hər dəfə yoxlamaq lazımdır.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app
from ingestion.cleaner import clean_text
from ingestion.ocr import extract_text

CATALOG_LINES = [
    "BRAVO SUPERMARKET",
    "Sud Milla 2.5% 1 L      1,89   2,45",
    "Duyu Basmati 1 kq       3,40",
    "Yag Sola 1.8 L          6,20   8,40",
    "Su Sirab 1,5 l          0,60",
]

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int = 34):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return None


@pytest.fixture(scope="module")
def catalog_image(tmp_path_factory) -> Path:
    font = _font()
    if font is None:
        pytest.skip("TrueType şrift tapılmadı - OCR testi ötürülür")

    img = Image.new("RGB", (1100, 420), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(CATALOG_LINES):
        draw.text((50, 40 + i * 68), line, fill="black", font=font)

    path = tmp_path_factory.mktemp("catalog") / "test_catalog.png"
    img.save(path)
    return path


def test_ocr_metni_oxuyur(catalog_image):
    result = extract_text(catalog_image)
    assert result.source_type == "image"
    assert result.ocr_used is True
    assert result.chars > 40, f"OCR demək olar heç nə oxumadı: {result.text!r}"


def test_ocr_neticesinden_qiymetler_cixir(catalog_image):
    result = extract_text(catalog_image)
    cleaned = clean_text(result.text)

    assert cleaned.lines, f"Heç bir məhsul sətri tapılmadı. Xam mətn:\n{result.text}"

    # OCR hərf səhvi edə bilər, amma qiymətlər tanınmalıdır
    prices = {round(line.price, 2) for line in cleaned.lines if line.price}
    assert prices & {1.89, 3.40, 6.20, 0.60}, f"Gözlənilən qiymətlər tapılmadı: {prices}"


def test_upload_endpoint_ucdan_uca(catalog_image):
    with TestClient(app) as client:
        with open(catalog_image, "rb") as f:
            res = client.post(
                "/api/catalogs/upload",
                files={"file": ("test_catalog.png", f, "image/png")},
                data={"store": "Test Market"},
            )
        assert res.status_code == 200, res.text
        data = res.json()
        catalog_id = data["catalog_id"]

        try:
            assert data["source_type"] == "image"
            assert data["stats"]["kept"] >= 1
            assert data["stats"]["total_lines"] >= data["stats"]["kept"]

            # Eyni fayl ikinci dəfə -> təkrar emal olunmamalıdır
            with open(catalog_image, "rb") as f:
                again = client.post(
                    "/api/catalogs/upload",
                    files={"file": ("test_catalog.png", f, "image/png")},
                    data={"store": "Test Market"},
                )
            assert again.json()["duplicate"] is True

            lines = client.get(f"/api/catalogs/{catalog_id}/lines").json()
            assert lines["store"] == "Test Market"
            assert len(lines["lines"]) >= 1
        finally:
            # Test datası real DB-də qalmasın
            client.delete(f"/api/catalogs/{catalog_id}")


def test_desteklenmeyen_fayl_reddedilir():
    with TestClient(app) as client:
        res = client.post(
            "/api/catalogs/upload",
            files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
            data={"store": "Test"},
        )
        assert res.status_code == 400
        assert "Dəstəklənməyən" in res.json()["detail"]


def test_bos_fayl_reddedilir():
    with TestClient(app) as client:
        res = client.post(
            "/api/catalogs/upload",
            files={"file": ("bos.png", b"", "image/png")},
            data={"store": "Test"},
        )
        assert res.status_code == 400


def test_qiymetli_kataloq_silinir():
    """
    Regres: qiyməti olan kataloq silinməli idi, amma xarici açar buraxmırdı.

    Səhv real işdə üzə çıxdı - n8n sınağından sonra kataloqu silmək istədik və
    endpoint 500 qaytardı. Səbəb: `prices.catalog_id` xarici açardır, sətirlər
    silinmədən kataloq silinə bilmir.
    """
    from app.db import db_cursor, get_connection

    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO stores (slug, name) VALUES ('silinen-test', 'Silinən Test') "
            "ON CONFLICT(slug) DO NOTHING"
        )
        cur.execute("SELECT id FROM stores WHERE slug = 'silinen-test'")
        store_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, source_type, status) "
            "VALUES (?, 'test-hash-sil', 'data/raw/yoxdur.png', 'image', 'parsed')",
            (store_id,),
        )
        catalog_id = cur.lastrowid
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key) "
            "VALUES ('test|silinen|1', 'Silinən məhsul', 'test|silinen|1')"
        )
        product_id = cur.lastrowid
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price) VALUES (?, ?, ?, 1.5)",
            (product_id, store_id, catalog_id),
        )

    with TestClient(app) as client:
        res = client.delete(f"/api/catalogs/{catalog_id}")
    assert res.status_code == 200, res.text

    conn = get_connection()
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM catalogs WHERE id = ?", (catalog_id,)
        ).fetchone()[0] == 0
        # Qiyməti qalmayan məhsul da qalmamalıdır
        assert conn.execute(
            "SELECT COUNT(*) FROM products WHERE id = ?", (product_id,)
        ).fetchone()[0] == 0
    finally:
        conn.close()

    with db_cursor() as cur:
        cur.execute("DELETE FROM stores WHERE slug = 'silinen-test'")
