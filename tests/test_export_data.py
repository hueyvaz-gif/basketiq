"""
DEPLOY DATA ARXİVİ (`tools/export_data.py`) - 2026-09-11.

Arxiv serverdə volume-a açılır; səhvi orada tutmaq gecdir - sayt ya boş, ya
sınıq şəkillərlə açılır. Testlər alətin üç vədini yoxlayır:
  - quruluş volume-unkudur və yetim xam fayl arxivə düşmür;
  - Windows kataloq yolları YALNIZ arxivdə çevrilir, lokal bazaya toxunulmur;
  - bazanın istinad etdiyi, amma çatmayan fayl tutulur.
"""

import fnmatch
import sqlite3
import tarfile
from pathlib import Path

import pytest

from app.config import settings
from tools.export_data import DEFAULT_OUT, build, portable_name

ROOT = Path(__file__).resolve().parent.parent

# (file_hash, bazadakı yol) - üç format da real bazada var (2026-09-11).
KATALOQLAR = [
    ("a" * 64, "raw\\aaaaaaaaaaaa_kat.pdf"),
    ("b" * 64, "data\\raw\\bbbbbbbbbbbb_kat.png"),
    ("c" * 64, "raw/cccccccccccc_kat.pdf"),
]


def _yaz(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


@pytest.fixture
def mühit(tmp_path):
    """Təcrid olunmuş mühit: real sxemli baza nüsxəsi + data + media qovluqları."""
    db = tmp_path / "mənbə.db"
    src = sqlite3.connect(settings.db_path)
    conn = sqlite3.connect(db)
    src.backup(conn)
    src.close()

    # Başqa testlərin sətirləri bu mühitə aid deyil - yalnız bizimkilər qalsın.
    for table in ("prices", "catalogs", "product_images", "ads"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("UPDATE products SET image_path = NULL")

    store = conn.execute(
        "INSERT INTO stores (slug, name) VALUES ('export-test', 'Export')"
    ).lastrowid
    for file_hash, path in KATALOQLAR:
        conn.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path) VALUES (?, ?, ?)",
            (store, file_hash, path),
        )
    product = conn.execute(
        "INSERT INTO products (canonical_key, name, image_path) "
        "VALUES ('export|test', 'Test', 'p900.jpg')"
    ).lastrowid
    conn.execute(
        "INSERT INTO product_images (product_id, image_path) VALUES (?, 'abc123.webp')",
        (product,),
    )
    reklam = (
        "INSERT INTO ads (advertiser, title, image_path, target_url, slot, starts_at, ends_at) "
        "VALUES ('X', 'Y', ?, 'https://example.com', 'home-rail-left', '2026-01-01', '2026-12-31')"
    )
    conn.execute(reklam, ("/static/images/ads/kreativ.webp",))
    # Nümunə banner yalnız repodakı statik qovluqdadır - yoxlama onu da tanımalıdır.
    conn.execute(reklam, ("/static/images/ads/sample-rail.svg",))
    conn.commit()
    conn.close()

    data = tmp_path / "data"
    for _, path in KATALOQLAR:
        _yaz(data / "raw" / portable_name(path), b"%PDF-test")
    _yaz(data / "raw" / "yetim_kat.pdf", b"yetim")
    _yaz(data / "text" / "aaaaaaaaaaaa.txt", b"ocr")
    _yaz(data / "cache" / "extract" / "k.json", b"{}")

    media = tmp_path / "media"
    for rel in ("images/ads/kreativ.webp", "images/products/p900.jpg", "product_images/abc123.webp"):
        _yaz(media / rel, b"img")
    _yaz(media / "product_images" / ".gitkeep", b"")

    return {"db": db, "data": data, "media": media, "out": tmp_path / "arxiv.tar.gz"}


def _build(m):
    return build(m["out"], db_path=m["db"], data_dir=m["data"], media_dir=m["media"])


def test_arxiv_volume_quruluşundadır_yetim_fayl_düşmür(mühit):
    r = _build(mühit)

    with tarfile.open(r.archive) as tar:
        names = set(tar.getnames())

    assert names == {
        "basketiq.db",
        "raw/aaaaaaaaaaaa_kat.pdf",
        "raw/bbbbbbbbbbbb_kat.png",
        "raw/cccccccccccc_kat.pdf",
        "text/aaaaaaaaaaaa.txt",
        "cache/extract/k.json",
        "media/images/ads/kreativ.webp",
        "media/images/products/p900.jpg",
        "media/product_images/abc123.webp",
    }
    assert r.counts["raw"] == 3 and r.counts["media/product_images"] == 1


def test_kataloq_yolları_yalnız_arxivdə_çevrilir(mühit, tmp_path):
    r = _build(mühit)
    assert r.fixed_paths == 2

    with tarfile.open(r.archive) as tar:
        tar.extract("basketiq.db", tmp_path / "açıq", filter="data")
    conn = sqlite3.connect(tmp_path / "açıq" / "basketiq.db")
    try:
        arxivdə = sorted(fp for (fp,) in conn.execute("SELECT file_path FROM catalogs"))
    finally:
        conn.close()
    assert arxivdə == [
        "raw/aaaaaaaaaaaa_kat.pdf",
        "raw/bbbbbbbbbbbb_kat.png",
        "raw/cccccccccccc_kat.pdf",
    ]

    conn = sqlite3.connect(mühit["db"])
    try:
        mənbədə = sorted(fp for (fp,) in conn.execute("SELECT file_path FROM catalogs"))
    finally:
        conn.close()
    assert mənbədə == sorted(p for _, p in KATALOQLAR), "lokal baza dəyişməməlidir"


def test_tam_arxiv_yoxlamadan_keçir(mühit):
    r = _build(mühit)

    assert r.integrity == "ok"
    assert r.missing == []
    assert r.ok


def test_bazanın_istinad_etdiyi_çatmayan_fayl_tutulur(mühit):
    (mühit["media"] / "images" / "products" / "p900.jpg").unlink()
    (mühit["data"] / "raw" / "bbbbbbbbbbbb_kat.png").unlink()

    r = _build(mühit)

    assert not r.ok
    assert "products: p900.jpg" in r.missing
    assert "kataloq: raw/bbbbbbbbbbbb_kat.png" in r.missing


@pytest.mark.parametrize("stored", ["raw\\x.pdf", "data\\raw\\x.pdf", "raw/x.pdf", "x.pdf"])
def test_kataloq_faylının_adı_hər_formatdan_çıxır(stored):
    assert portable_name(stored) == "x.pdf"


def test_arxiv_repoya_və_image_ə_düşmür():
    """Arxivdə baza var: commit olunsa tarixçədə, image-ə düşsə registry-də qalar."""
    for fayl in (".gitignore", ".dockerignore"):
        sətirlər = (ROOT / fayl).read_text(encoding="utf-8").splitlines()
        nümunələr = [s for s in sətirlər if s and not s.startswith(("#", "!"))]
        assert any(fnmatch.fnmatch(DEFAULT_OUT.name, n) for n in nümunələr), fayl
