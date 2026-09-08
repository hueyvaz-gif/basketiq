"""
Scraper testləri.

ŞƏBƏKƏYƏ ÇIXMIRIQ. Səbəb: test real saytdan asılı olsa, sayt dəyişəndə və ya
internet olmayanda test qırılır - halbuki BİZİM kodumuzda heç nə pozulmayıb.
Ona görə HTTP funksiyalarını əvəz edirik (monkeypatch) və yalnız öz məntiqimizi
yoxlayırıq: link tapma, təkrar yoxlaması, robots qadağası, xəta hesabatı.
"""

import pytest
from fastapi.testclient import TestClient

from app.db import db_cursor, get_connection
from app.main import app
from ingestion import scraper
from ingestion.ingest import text_path_for
from ingestion.scraper import (
    ScrapeError,
    Source,
    filename_from_url,
    find_catalog_links,
    scrape_source,
)

CATALOG_HTML = """
<html><body>
  <a href="/haqqimizda">Haqqımızda</a>
  <a href="/files/endirim-jurnali.pdf">Endirim jurnalı</a>
  <a href="https://cdn.example.az/kataloq/aksiya.pdf?v=3">Aksiya</a>
  <img src="/images/logo.png">
  <img src="/images/kataloq-sentyabr.jpg">
  <a href="/files/qaydalar.docx">Qaydalar</a>
</body></html>
"""


# ------------------------------------------------------------------ link tapma


def test_pdf_ve_kataloq_sekilleri_tapilir():
    links = find_catalog_links(CATALOG_HTML, "https://example.az/kataloq")
    assert "https://example.az/files/endirim-jurnali.pdf" in links
    assert "https://cdn.example.az/kataloq/aksiya.pdf?v=3" in links
    # URL-ində kataloq sözü olan şəkil götürülür
    assert "https://example.az/images/kataloq-sentyabr.jpg" in links


def test_adi_menyu_linkleri_ve_logo_goturulmur():
    links = find_catalog_links(CATALOG_HTML, "https://example.az/kataloq")
    assert not any("haqqimizda" in u for u in links)
    assert not any("logo.png" in u for u in links)
    assert not any("qaydalar" in u for u in links)


def test_pdf_sekilden_evvel_gelir():
    """PDF-in text layer şansı var - OCR-siz keçə bilər, ona görə üstündür."""
    links = find_catalog_links(CATALOG_HTML, "https://example.az/kataloq")
    first_image = next(i for i, u in enumerate(links) if u.endswith(".jpg"))
    last_pdf = max(i for i, u in enumerate(links) if ".pdf" in u)
    assert last_pdf < first_image


def test_url_den_fayl_adi():
    assert filename_from_url("https://a.az/files/jurnal.pdf") == "jurnal.pdf"
    assert filename_from_url("https://a.az/storage/file/") == "catalog.pdf"
    assert filename_from_url("https://a.az/x/01ABC.pdf?v=2") == "01ABC.pdf"


# ------------------------------------------------------------------ nəzakət


def test_robots_qadagasi_yuklemeni_dayandirir(monkeypatch):
    monkeypatch.setattr(scraper, "robots_allows", lambda url: False)
    with pytest.raises(ScrapeError, match="robots.txt"):
        scraper.download("https://example.az/kataloq.pdf")
    with pytest.raises(ScrapeError, match="robots.txt"):
        scraper.fetch_html("https://example.az/kataloq")


def test_nameluм_menbe_aydin_xeta_verir():
    with pytest.raises(ScrapeError, match="Naməlum mənbə"):
        scrape_source("belə-market-yoxdur")


# ------------------------------------------------------------------ uçdan-uca


@pytest.fixture
def fake_source(monkeypatch):
    """Şəbəkəsiz mənbə: HTML və PNG bayt sabitdir."""
    from PIL import Image, ImageDraw
    import io

    img = Image.new("RGB", (900, 300), "white")
    ImageDraw.Draw(img).text((40, 40), "Sud Milla 1 L 1,89 2,45", fill="black")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    content = buffer.getvalue()

    source = Source(key="test", store="Test Scrape Market",
                    page_url="https://example.az/kataloq")
    monkeypatch.setitem(scraper.SOURCES, "test", source)
    monkeypatch.setattr(scraper, "robots_allows", lambda url: True)
    monkeypatch.setattr(
        scraper, "fetch_html",
        lambda url, use_selenium=False: (
            '<a href="/files/kataloq-sentyabr.png">Kataloq</a>', False
        ),
    )
    monkeypatch.setattr(scraper, "download", lambda url, max_mb=None: content)
    return source


def _cleanup(catalog_id: int) -> None:
    conn = get_connection()
    row = conn.execute(
        "SELECT file_hash, file_path FROM catalogs WHERE id = ?", (catalog_id,)
    ).fetchone()
    conn.close()
    if row:
        from app.config import settings
        (settings.base_dir / row["file_path"]).unlink(missing_ok=True)
        text_path_for(row["file_hash"]).unlink(missing_ok=True)
    with db_cursor() as cur:
        cur.execute("DELETE FROM prices WHERE catalog_id = ?", (catalog_id,))
        cur.execute("DELETE FROM catalogs WHERE id = ?", (catalog_id,))


def test_scraping_kataloqu_db_ye_yazir(fake_source):
    report = scrape_source("test", max_files=1, max_pages=1)
    assert not report.errors, report.errors
    assert len(report.ingested) == 1

    item = report.ingested[0]
    catalog_id = item["catalog_id"]
    try:
        assert item["source_url"].endswith("kataloq-sentyabr.png")
        conn = get_connection()
        row = conn.execute(
            "SELECT source_url, s.name AS store FROM catalogs c "
            "JOIN stores s ON s.id = c.store_id WHERE c.id = ?", (catalog_id,)
        ).fetchone()
        conn.close()
        assert row["store"] == "Test Scrape Market"
        assert row["source_url"].endswith("kataloq-sentyabr.png")
    finally:
        _cleanup(catalog_id)


def test_eyni_url_ikinci_defe_endirilmir(fake_source):
    first = scrape_source("test", max_files=1, max_pages=1)
    catalog_id = first.ingested[0]["catalog_id"]
    try:
        second = scrape_source("test", max_files=1, max_pages=1)
        assert second.ingested == []
        assert len(second.skipped) == 1
        assert second.skipped[0]["catalog_id"] == catalog_id
        assert "URL" in second.skipped[0]["reason"]
    finally:
        _cleanup(catalog_id)


def test_link_tapilmasa_aydin_xeta(monkeypatch):
    monkeypatch.setitem(
        scraper.SOURCES, "bos",
        Source(key="bos", store="Boş", page_url="https://example.az/bos"),
    )
    monkeypatch.setattr(scraper, "robots_allows", lambda url: True)
    monkeypatch.setattr(
        scraper, "fetch_html", lambda url, use_selenium=False: ("<html></html>", False)
    )
    report = scrape_source("bos")
    assert report.ingested == []
    assert any("Kataloq linki tapılmadı" in e for e in report.errors)


# ------------------------------------------------------------------ API


def test_menbe_siyahisi_endpointi():
    with TestClient(app) as client:
        res = client.get("/api/scrape/sources")
        assert res.status_code == 200
        keys = {item["key"] for item in res.json()}
        assert "araz" in keys
        # OBA BasketIQ v2-də mənbə siyahısından çıxarıldı (bazadakı köhnə
        # sətirləri qalır, amma yeni çəkiliş olmur) - siyahıya qayıtmamalıdır.
        assert "oba" not in keys


def test_nameluм_menbe_400_qaytarir():
    with TestClient(app) as client:
        res = client.post("/api/scrape/yoxdur")
        assert res.status_code == 400
        assert "Naməlum mənbə" in res.json()["detail"]
