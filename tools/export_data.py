"""
Deploy üçün DATA ARXİVİ: baza + xam kataloqlar + OCR mətni + LLM keşi + şəkillər.

    python -m tools.export_data                          # -> basketiq-data.tar.gz
    python -m tools.export_data --out /yol/arxiv.tar.gz

NİYƏ LAZIMDIR? Baza və şəkillər repoda YOXDUR (`.gitignore`) - təmiz
`git clone`-dan sayt boş açılır. Arxiv serverdəki volume-un quruluşundadır
(`/data`, bax deploy/README.md «İlk deploy») və bir əmrlə oraya açılır:

    basketiq.db
    raw/<kataloq faylı>        yalnız bazanın istinad etdiyi
    text/<hash12>.txt          OCR mətni
    cache/...                  LLM keşi - serverdə yenidən emal lazım olmur
    media/images/ads/          reklam kreativləri     (MEDIA_DIR=/data/media)
    media/images/products/     kataloq kəsikləri
    media/product_images/      sayt məhsul fotoları

ƏL İLƏ `cp` NİYƏ KİFAYƏT DEYİL (2026-09-11, ilk arxivdə tapıldı):
  1. BAZA ANLIQ NÜSXƏ İLƏ götürülür (SQLite backup API): server və ya n8n
     həmin an yazırsa, `cp` yarımçıq səhifəli fayl verə bilər.
  2. KATALOQ YOLLARI WINDOWS FORMATINDADIR (`raw\\x.pdf`, `data\\raw\\x.pdf`).
     Linux-da `\\` ayırıcı deyil, adın hissəsidir: 7 kataloqun heç birinin xam
     faylı serverdə tapılmırdı - silmə və yenidən emal qırılırdı. Yollar
     YALNIZ ARXİVDƏKİ NÜSXƏDƏ `raw/<ad>` olur (`store_path`-in yeni formatı,
     DATA_DIR-ə nisbi); lokal bazaya toxunulmur.
  3. YETİM XAM FAYL arxivə düşmür: bazanın istinad etmədiyi kataloq faylı
     serverdə yalnız yer tutardı.

ARXİV SONDA AÇILIB YOXLANILIR: bazanın bütövlüyü (`integrity_check`) və bazanın
istinad etdiyi HƏR faylın arxivdə olması. Çatmayan varsa, çıxış kodu 1-dir -
yarımçıq arxivi serverə aparmaqdansa, burada dayanmaq yaxşıdır.
"""

import argparse
import hashlib
import sqlite3
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from app.config import settings
from ingestion.ingest import text_path_for

DEFAULT_OUT = settings.base_dir / "basketiq-data.tar.gz"
STATIC_DIR = settings.base_dir / "app" / "static"

# Media qovluğunun alt qovluqları -> arxivdə `media/<alt>`. Yazan tərəflər:
# app/api/ads.py (kreativ), ingestion/images.py (kəsik),
# app/services/product_images.py (foto).
MEDIA_SUBDIRS = ("images/ads", "images/products", "product_images")


@dataclass
class Result:
    archive: Path
    fixed_paths: int                       # Windows formatından çevrilən kataloq yolu
    counts: dict[str, int]                 # arxivdəki fayl sayı - qrup üzrə
    integrity: str = ""
    missing: list[str] = field(default_factory=list)   # bazanın istinad etdiyi, arxivdə olmayan

    @property
    def ok(self) -> bool:
        return self.integrity == "ok" and not self.missing


def _group(arcname: str) -> str:
    """`media/images/ads/x.webp` -> `media/images/ads`; `cache/extract/k.json` -> `cache`."""
    parts = arcname.split("/")
    return "/".join(parts[:-1]) if parts[0] == "media" else parts[0]


def portable_name(stored: str) -> str:
    """`data\\raw\\x.pdf`, `raw\\x.pdf`, `raw/x.pdf` -> `x.pdf`."""
    return stored.replace("\\", "/").rsplit("/", 1)[-1]


def snapshot(db_path: Path, dst: Path) -> tuple[list[str], list[str], int]:
    """
    Bazanın anlıq nüsxəsini `dst`-yə yazır və NÜSXƏDƏ kataloq yollarını
    daşınan formata (`raw/<ad>`) çevirir.

    Qaytarır: xam fayl adları, OCR mətn faylı adları, çevrilən yol sayı.
    """
    src = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    conn = sqlite3.connect(dst)
    try:
        src.backup(conn)
        raw, text, fixed = [], [], 0
        for catalog_id, stored, file_hash in conn.execute(
            "SELECT id, file_path, file_hash FROM catalogs ORDER BY id"
        ).fetchall():
            name = portable_name(stored)
            if stored != f"raw/{name}":
                conn.execute(
                    "UPDATE catalogs SET file_path = ? WHERE id = ?", (f"raw/{name}", catalog_id)
                )
                fixed += 1
            raw.append(name)
            text.append(text_path_for(file_hash).name)
        conn.commit()
        conn.execute("VACUUM")
        return raw, text, fixed
    finally:
        conn.close()
        src.close()


def collect(
    db_copy: Path, raw: list[str], text: list[str], data_dir: Path, media_dir: Path
) -> dict[str, Path]:
    """Arxiv adı -> diskdəki fayl. Olmayan fayl burada ATLANIR - `verify` onu tutur."""
    entries = {"basketiq.db": db_copy}
    for name in raw:
        if (data_dir / "raw" / name).is_file():
            entries[f"raw/{name}"] = data_dir / "raw" / name
    for name in text:
        if (data_dir / "text" / name).is_file():
            entries[f"text/{name}"] = data_dir / "text" / name
    cache = data_dir / "cache"
    if cache.is_dir():
        for path in sorted(cache.rglob("*")):
            if path.is_file():
                entries["cache/" + path.relative_to(cache).as_posix()] = path
    for sub in MEDIA_SUBDIRS:
        folder = media_dir / sub
        if folder.is_dir():
            for path in sorted(folder.iterdir()):
                if path.is_file() and path.name != ".gitkeep":
                    entries[f"media/{sub}/{path.name}"] = path
    return entries


def verify(archive: Path, static_dir: Path = STATIC_DIR) -> tuple[str, list[str]]:
    """
    Arxivi müvəqqəti qovluğa açıb serverdəki kimi oxuyur.

    Reklam şəkli repodakı statik qovluqda da ola bilər (nümunə bannerlər
    image-ə kodla birlikdə düşür), ona görə `static_dir` də yoxlanılır.
    """
    with tempfile.TemporaryDirectory(prefix="bq-check-") as tmp:
        root = Path(tmp)
        with tarfile.open(archive) as tar:
            tar.extractall(root, filter="data")
        conn = sqlite3.connect(root / "basketiq.db")
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            missing = []
            for (stored,) in conn.execute("SELECT file_path FROM catalogs"):
                if "\\" in stored or not (root / PurePosixPath(stored)).is_file():
                    missing.append(f"kataloq: {stored}")
            for (url,) in conn.execute("SELECT image_path FROM ads WHERE image_path IS NOT NULL"):
                if not url.startswith("/static/"):
                    continue
                rel = url.removeprefix("/static/")
                if not ((root / "media" / rel).is_file() or (static_dir / rel).is_file()):
                    missing.append(f"reklam: {url}")
            for table, folder in (("products", "images/products"), ("product_images", "product_images")):
                for (name,) in conn.execute(
                    f"SELECT DISTINCT image_path FROM {table} WHERE image_path IS NOT NULL"
                ):
                    if not (root / "media" / folder / name).is_file():
                        missing.append(f"{table}: {name}")
            return integrity, missing
        finally:
            # Windows-da açıq fayl qovluğun silinməsinə imkan vermir.
            conn.close()


def build(
    out: Path = DEFAULT_OUT,
    *,
    db_path: Path | None = None,
    data_dir: Path | None = None,
    media_dir: Path | None = None,
    static_dir: Path = STATIC_DIR,
) -> Result:
    db_path = db_path or settings.db_path
    data_dir = data_dir or settings.data_dir
    media_dir = media_dir or settings.media_dir

    with tempfile.TemporaryDirectory(prefix="bq-export-") as tmp:
        db_copy = Path(tmp) / "basketiq.db"
        raw, text, fixed = snapshot(db_path, db_copy)
        entries = collect(db_copy, raw, text, data_dir, media_dir)

        # Əvvəl `.part`-a yazılır: yarıda qırılan yığım köhnə, işlək arxivin
        # yerini tutmasın.
        partial = out.with_name(out.name + ".part")
        with tarfile.open(partial, "w:gz") as tar:
            for arcname, path in entries.items():
                tar.add(path, arcname=arcname, recursive=False)
        partial.replace(out)

    counts: dict[str, int] = {}
    for arcname in entries:
        counts[_group(arcname)] = counts.get(_group(arcname), 0) + 1

    integrity, missing = verify(out, static_dir)
    return Result(out, fixed, counts, integrity, missing)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy üçün data arxivi (baza + şəkillər)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="arxivin yolu")
    args = parser.parse_args(argv)

    result = build(args.out)
    print(f"Arxiv: {result.archive}  ({result.archive.stat().st_size / 1024 / 1024:.1f} MB)")
    for group, n in result.counts.items():
        print(f"  {group:<24} {n} fayl")
    print(f"Kataloq yolu daşınan formata çevrildi: {result.fixed_paths}")
    print(f"Bazanın bütövlüyü: {result.integrity}")
    if result.missing:
        print("\nBAZANIN İSTİNAD ETDİYİ, ARXİVDƏ OLMAYAN FAYLLAR:")
        for item in result.missing:
            print(f"  {item}")
        return 1
    digest = hashlib.sha256(result.archive.read_bytes()).hexdigest()
    print(f"Bazanın istinad etdiyi bütün fayllar arxivdədir.\nsha256: {digest}")
    print("Serverə köçürəndən sonra `sha256sum` ilə müqayisə et (deploy/README.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
