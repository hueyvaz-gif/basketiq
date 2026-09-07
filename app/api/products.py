"""Çıxarılmış məhsullar və keş statistikası."""

from fastapi import APIRouter

from ai import cache
from app.db import get_connection
from ingestion.pipeline import load_products

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/products")
def products(limit: int = 200):
    return {"items": load_products(limit=limit)}


@router.get("/products/search")
def search_products(q: str = "", limit: int = 20):
    """Səbətə məhsul əlavə etmək üçün axtarış."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT p.id, p.name, p.brand, p.size_value, p.size_unit, p.category, "
            "       p.group_key, COUNT(DISTINCT pr.store_id) AS store_count "
            "FROM products p LEFT JOIN prices pr ON pr.product_id = p.id "
            "WHERE p.name LIKE ? OR COALESCE(p.brand,'') LIKE ? "
            "GROUP BY p.id ORDER BY store_count DESC, p.name LIMIT ?",
            (f"%{q}%", f"%{q}%", limit),
        ).fetchall()
        return {"items": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/cache/stats")
def cache_stats():
    """Keşdə neçə sətir var? Dashboard-da göstərilir ki, qənaəti görəsən."""
    return cache.stats()


@router.delete("/cache")
def cache_clear():
    """Prompt üzərində işləyərkən keşi təmizləmək lazım ola bilər."""
    return {"deleted": cache.clear()}
