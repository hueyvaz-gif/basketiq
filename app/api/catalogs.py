"""
Kataloq endpoint-ləri: manual upload, siyahı, çıxarılmış sətirlər.

Bu, pipeline-ın BİRİNCİ mərhələsidir:
    fayl -> mətn -> təmiz sətirlər
LLM hələ işə qarışmır (Həftə 2). Belədə OCR keyfiyyətini əvvəlcə öz gözünlə
görürsən - modelin nə ilə qidalandığını bilməmək ən böyük səhvdir.

Emal məntiqi özü burada DEYİL - `ingestion/ingest.py`-dədir, çünki eyni
məntiqi scraper də işlədir. Bu fayl yalnız HTTP qatıdır.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import settings
from app.security import require_admin
from app.db import db_cursor, get_connection
from ingestion.cleaner import clean_text
from ingestion.profiles import profile_for_store_name
from ingestion.ingest import (  # noqa: F401  (slugify/get_or_create_store xaricdən də işlənir)
    IngestError,
    get_or_create_store,
    ingest_bytes,
    resolve_path,
    safe_filename,
    slugify,
    text_path_for,
)
from ingestion.pipeline import extract_catalog

# ADMİN SƏTHİ (B11): panel bağlı olanda bütün endpoint-lər 404 qaytarır.
# Qapı ROUTER səviyyəsindədir - yeni endpoint əlavə edən onu ayrıca
# qorumağı unuda bilməz.
router = APIRouter(prefix="/api/catalogs", tags=["catalogs"], dependencies=[Depends(require_admin)])


# ------------------------------------------------------------------ endpoint-lər


@router.post("/upload")
async def upload_catalog(
    file: UploadFile = File(...),
    store: str = Form("Naməlum market"),
    force_ocr: bool = Form(False),
    psm: int = Form(0),  # 0 = .env-dəki default
):
    """
    Kataloq faylını qəbul edir, mətni çıxarır, təmizləyir və DB-yə yazır.

    Eyni fayl ikinci dəfə yüklənsə (SHA-256 eynidir) təkrar emal olunmur -
    OCR bahalı əməliyyatdır, boş yerə təkrarlamırıq.
    """
    content = await file.read()

    # MARKETİN EMAL PROFİLİ (D14): forma «avtomatik» seçilibsə (psm=0),
    # marketə xas ölçülmüş ayar işə düşür. Beləcə əl ilə yüklənən kataloq da
    # avtomatik çəkilişlə EYNİ qaydalarla oxunur - iki axının nəticəsi
    # bir-birindən fərqlənmir.
    profile = profile_for_store_name(store)
    try:
        result = ingest_bytes(
            content=content,
            filename=file.filename or "catalog",
            store=store,
            force_ocr=force_ocr or bool(profile and profile.force_ocr),
            psm=psm if psm > 0 else (profile.psm if profile else None),
            max_pages=profile.max_pages if profile else None,
        )
    except IngestError as e:
        raise HTTPException(e.status, e.message)

    return result.as_dict()


@router.get("")
def list_catalogs():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT c.id, c.file_hash, c.file_path, c.source_url, c.source_type, "
            "       c.status, c.fetched_at, s.name AS store_name "
            "FROM catalogs c JOIN stores s ON s.id = c.store_id "
            "ORDER BY c.id DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _load_catalog(catalog_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT c.*, s.name AS store_name FROM catalogs c "
            "JOIN stores s ON s.id = c.store_id WHERE c.id = ?",
            (catalog_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Kataloq tapılmadı")
    return row


@router.get("/{catalog_id}/lines")
def catalog_lines(catalog_id: int, limit: int = 200):
    """Təmizlənmiş sətirlər + statistika. UI bunu cədvəldə göstərir."""
    row = _load_catalog(catalog_id)
    path = text_path_for(row["file_hash"])
    if not path.exists():
        raise HTTPException(404, "Mətn faylı tapılmadı - kataloqu yenidən yüklə")

    cleaned = clean_text(path.read_text(encoding="utf-8"))
    return {
        "catalog_id": catalog_id,
        "store": row["store_name"],
        "source_type": row["source_type"],
        "stats": cleaned.stats,
        "lines": [ln.to_dict() for ln in cleaned.lines[:limit]],
    }


@router.post("/{catalog_id}/extract")
def extract_catalog_endpoint(catalog_id: int, limit: int = 10, use_cache: bool = True):
    """
    Kataloqun sətirlərini AI ilə struktur məhsullara çevirir.

    limit=10 defolt olaraq qoyulub: GPU-suz maşında hər sətir ~10 saniyə çəkir.
    Əvvəlcə 10 sətirlə yoxlayırsan, nəticə düzgündürsə limiti artırırsan.
    Keş sayəsində təkrar emal pulsuzdur.
    """
    row = _load_catalog(catalog_id)
    path = text_path_for(row["file_hash"])
    if not path.exists():
        raise HTTPException(404, "Mətn faylı tapılmadı - kataloqu yenidən yüklə")

    result = extract_catalog(
        catalog_id=catalog_id,
        text=path.read_text(encoding="utf-8"),
        store_id=row["store_id"],
        store_name=row["store_name"],
        limit=limit if limit > 0 else None,
        use_cache=use_cache,
    )
    return result.as_dict()


@router.get("/{catalog_id}/text")
def catalog_text(catalog_id: int, limit: int = 4000):
    """Xam OCR mətni - "AI nə oxudu?" sualına cavab vermək üçün."""
    row = _load_catalog(catalog_id)
    path = text_path_for(row["file_hash"])
    if not path.exists():
        raise HTTPException(404, "Mətn faylı tapılmadı")
    return {"catalog_id": catalog_id, "text": path.read_text(encoding="utf-8")[:limit]}


@router.delete("/{catalog_id}")
def delete_catalog(catalog_id: int):
    """Sınaq zamanı lazımdır: kataloqu və onun fayllarını silir."""
    row = _load_catalog(catalog_id)

    raw_file = resolve_path(row["file_path"])
    if raw_file.is_file() and settings.raw_dir in raw_file.parents:
        raw_file.unlink(missing_ok=True)
    text_path_for(row["file_hash"]).unlink(missing_ok=True)

    with db_cursor() as cur:
        # Əvvəlcə qiymətlər: prices.catalog_id xarici açardır, sətirlər qalarsa
        # kataloqun silinməsi "FOREIGN KEY constraint failed" ilə qırılır.
        cur.execute("DELETE FROM prices WHERE catalog_id = ?", (catalog_id,))
        cur.execute("DELETE FROM catalogs WHERE id = ?", (catalog_id,))
        # Heç bir qiyməti qalmayan məhsul artıq mövcud deyil - onu saxlamaq
        # səbət axtarışında "qiymətsiz məhsul" kimi görünərdi.
        #
        # HƏR İKİ QAT YOXLANILIR (2026-09-10-da düzəldildi).
        #
        # Əvvəl yalnız `prices` sayılırdı. `price_snapshots` boş olduğu
        # müddətdə bu fərq görünmürdü, amma mağaza qatı dolan kimi sətir
        # TƏHLÜKƏLİ oldu: Bravonun 13 089 məhsulunun `prices` sətri yoxdur -
        # onlar YALNIZ snapshot-dadır. Yəni İSTƏNİLƏN kataloqu silmək həmin
        # 13 min məhsulu silməyə cəhd edirdi.
        #
        # Praktikada `DELETE /api/catalogs/{id}` 500 qaytarırdı
        # (`price_snapshots.product_id` xarici açardır və silinməyə imkan
        # vermir). Xarici açar yoxlaması sönülü olsaydı, səhv SƏSSİZ olardı
        # və mağaza qatı bir kataloq silinməsi ilə yox olardı.
        cur.execute(
            "DELETE FROM products "
            " WHERE id NOT IN (SELECT product_id FROM prices) "
            "   AND id NOT IN (SELECT product_id FROM price_snapshots)"
        )

    return {"deleted": catalog_id}
