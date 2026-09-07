"""
Ortaq "ingest" mərhələsi: BAYT -> mətn -> təmiz sətirlər -> DB sətri.

Niyə ayrıca fayl? Kataloq iki yolla gəlir:
    1. istifadəçi əl ilə yükləyir   (app/api/catalogs.py)
    2. scraper saytdan çəkir        (ingestion/scraper.py)

Bundan sonrakı addımlar hər ikisi üçün EYNİDİR: hash, təkrar yoxlaması, OCR,
təmizləmə, DB-yə yazma. Bu məntiqi iki yerdə saxlasaq, biri dəyişəndə digəri
sükutla köhnəlir - ona görə bir yerə yığılıb.

Bu qat FastAPI-dən asılı DEYİL (HTTPException import etmir). Səbəb: scraper
konsoldan da işə düşür; veb çərçivəsi ingest məntiqinə qarışmamalıdır. Xətanı
IngestError kimi qaldırırıq, API onu HTTPException-a çevirir.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.db import db_cursor, get_connection
from ingestion.cleaner import clean_text
from ingestion.ocr import SUPPORTED_SUFFIXES, extract_text, file_sha256

# Azərbaycan hərfləri -> ASCII (slug üçün). "Bravo Şəhər" -> "bravo-seher"
_AZ_MAP = str.maketrans("əöüğışçƏÖÜĞIŞÇİ", "eougiscEOUGISCI")


class IngestError(Exception):
    """status: HTTP kodu kimi işlənə bilər (400 istifadəçi səhvi, 500 sistem)."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class IngestResult:
    catalog_id: int
    store: str
    duplicate: bool = False
    filename: str = ""
    size_mb: float = 0.0
    source_type: str = ""
    ocr_used: bool = False
    pages: int = 0
    chars: int = 0
    source_url: str | None = None
    message: str = ""
    notes: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    preview: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        if self.duplicate:
            # Təkrar halda ağır sahələr hesablanmayıb - onları qaytarmırıq
            return {
                "duplicate": True,
                "catalog_id": self.catalog_id,
                "store": self.store,
                "message": self.message,
            }
        return {
            "duplicate": False,
            "catalog_id": self.catalog_id,
            "store": self.store,
            "filename": self.filename,
            "size_mb": round(self.size_mb, 2),
            "source_type": self.source_type,
            "ocr_used": self.ocr_used,
            "pages": self.pages,
            "chars": self.chars,
            "source_url": self.source_url,
            "notes": self.notes,
            "stats": self.stats,
            "preview": self.preview,
        }


# ---------------------------------------------------------------- yardımçılar


def slugify(name: str) -> str:
    name = name.translate(_AZ_MAP)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return name or "market"


def safe_filename(name: str) -> str:
    """Faylın adı ilə qovluqdan kənara çıxmağın (path traversal) qarşısını alır."""
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:80] or "catalog"


def get_or_create_store(store_name: str) -> int:
    slug = slugify(store_name)
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM stores WHERE slug = ?", (slug,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO stores (slug, name) VALUES (?, ?)", (slug, store_name.strip())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def text_path_for(file_hash: str) -> Path:
    return settings.text_dir / f"{file_hash[:12]}.txt"


def store_path(path: Path) -> str:
    """
    Faylın bazada saxlanacaq yolu - DATA_DIR-ə görə nisbi.

    Niyə layihə kökünə görə deyil? Konteynerdə data qalıcı volume-dadır
    (`/data`), kod isə `/app`-də. Kökə görə nisbi yol orada ümumiyyətlə
    hesablanmır: "'/data/raw/x.png' is not in the subpath of '/app'".
    """
    try:
        return str(path.relative_to(settings.data_dir))
    except ValueError:
        return str(path)


def resolve_path(stored: str) -> Path:
    """
    Bazadakı yolu real fayla çevirir.

    Köhnə sətirlər layihə kökünə görə yazılıb ("data/raw/x.png"), yeniləri
    DATA_DIR-ə görə ("raw/x.png"). Hər ikisi işləməlidir - baza silinmədən
    yenilənir.
    """
    path = Path(stored)
    if path.is_absolute():
        return path
    candidate = settings.data_dir / path
    if candidate.exists():
        return candidate
    return settings.base_dir / path


def find_by_hash(file_hash: str):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT c.id, c.file_path, c.source_type, s.name AS store_name "
            "FROM catalogs c JOIN stores s ON s.id = c.store_id "
            "WHERE c.file_hash = ?",
            (file_hash,),
        ).fetchone()
    finally:
        conn.close()


def find_by_source_url(source_url: str):
    """
    Scraping üçün: bu URL artıq çəkilibmi?

    Niyə hash kifayət etmir? Hash yalnız fayl ENDİRİLDİKDƏN sonra bilinir.
    URL yoxlaması 9 MB-lıq PDF-i boş yerə endirməkdən xilas edir.
    """
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT c.id, c.status, s.name AS store_name FROM catalogs c "
            "JOIN stores s ON s.id = c.store_id WHERE c.source_url = ?",
            (source_url,),
        ).fetchone()
    finally:
        conn.close()


# ---------------------------------------------------------------- əsas funksiya


def ingest_bytes(
    content: bytes,
    filename: str,
    store: str,
    source_url: str | None = None,
    force_ocr: bool = False,
    psm: int | None = None,
    max_pages: int | None = None,
    preview_lines: int = 15,
) -> IngestResult:
    """
    Kataloq faylının baytlarını qəbul edir və emal zəncirini sona qədər aparır.

    Eyni fayl ikinci dəfə gəlsə (SHA-256 eynidir) yenidən emal olunmur -
    OCR bahalı əməliyyatdır, boş yerə təkrarlamırıq.
    """
    settings.ensure_dirs()

    original = safe_filename(filename or "catalog")
    suffix = Path(original).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IngestError(
            f"Dəstəklənməyən fayl tipi: '{suffix}'. "
            f"İcazəli: {', '.join(sorted(SUPPORTED_SUFFIXES))}",
            400,
        )

    if not content:
        raise IngestError("Fayl boşdur", 400)

    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise IngestError(
            f"Fayl çox böyükdür: {size_mb:.1f} MB (limit {settings.max_upload_mb} MB)",
            413,
        )

    # Müvəqqəti ad ilə yazırıq, hash-i hesablayırıq, sonra adını dəyişirik
    tmp_path = settings.raw_dir / f"_tmp_{original}"
    tmp_path.write_bytes(content)
    file_hash = file_sha256(tmp_path)

    existing = find_by_hash(file_hash)
    if existing:
        tmp_path.unlink(missing_ok=True)
        return IngestResult(
            catalog_id=existing["id"],
            store=existing["store_name"],
            duplicate=True,
            message=(
                f"Bu fayl artıq yüklənib ({existing['store_name']}) - "
                f"təkrar emal olunmadı."
            ),
        )

    final_path = settings.raw_dir / f"{file_hash[:12]}_{original}"
    tmp_path.replace(final_path)

    try:
        result = extract_text(
            final_path, force_ocr=force_ocr, psm=psm, max_pages=max_pages
        )
    except Exception as e:
        final_path.unlink(missing_ok=True)
        raise IngestError(f"Mətn çıxarıla bilmədi: {type(e).__name__}: {e}", 500)

    text_path_for(file_hash).write_text(result.text, encoding="utf-8")
    cleaned = clean_text(result.text)

    store_id = get_or_create_store(store)
    status = "parsed" if cleaned.lines else "empty"

    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, source_url, "
            "                      source_type, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                store_id,
                file_hash,
                store_path(final_path),
                source_url,
                result.source_type,
                status,
            ),
        )
        catalog_id = cur.lastrowid

    return IngestResult(
        catalog_id=catalog_id,
        store=store,
        duplicate=False,
        filename=original,
        size_mb=size_mb,
        source_type=result.source_type,
        ocr_used=result.ocr_used,
        pages=result.pages,
        chars=result.chars,
        source_url=source_url,
        notes=result.notes,
        stats=cleaned.stats,
        preview=[ln.to_dict() for ln in cleaned.lines[:preview_lines]],
    )
