"""Çıxarılmış məhsullar və keş statistikası."""

from fastapi import APIRouter

from ai import cache
from app.db import get_connection
from app.search_norm import match_score, tokens
from ingestion.pipeline import load_products

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/products")
def products(limit: int = 200):
    return {"items": load_products(limit=limit)}


@router.get("/products/search")
def search_products(q: str = "", limit: int = 20):
    """
    Səbətə məhsul əlavə etmək üçün axtarış.

    EYNİ NORMALLAŞDIRMA, EYNİ PİLLƏLƏR (M1). Bu endpoint ilə `/api/catalog/search`
    iki ayrı ekranı qidalandırır, amma qaydaları eyni olmalıdır: istifadəçi
    «dusbere» yazanda hər iki yerdə eyni nəticəni gözləyir. Ona görə hər ikisi
    `app/search_norm.py`-dan qidalanır.
    """
    sorğu_tokenləri = tokens(q)
    conn = get_connection()
    try:
        where = []
        params: list = []
        for token in sorğu_tokenləri:
            where.append("p.name_norm LIKE ?")
            params.append(f"%{token}%")

        sql = (
            "SELECT p.id, p.name, p.brand, p.size_value, p.size_unit, p.category, "
            "       p.group_key, p.name_norm, COUNT(DISTINCT pr.store_id) AS store_count "
            "FROM products p LEFT JOIN prices pr ON pr.product_id = p.id "
            + (f"WHERE {' AND '.join(where)} " if where else "")
            + "GROUP BY p.id ORDER BY store_count DESC, p.name"
        )
        rows = conn.execute(sql, tuple(params)).fetchall()

        if sorğu_tokenləri:
            ballı = [
                (match_score(r["name_norm"] or "", sorğu_tokenləri), r) for r in rows
            ]
            ballı = [(b, r) for b, r in ballı if b is not None]

            # Yazı səhvi keçidi: yalnız dəqiq nəticə OLMAYANDA (bax
            # `app/catalog.py:_rank_matches` - səbəb eynidir).
            if not ballı:
                hamısı = conn.execute(
                    "SELECT p.id, p.name, p.brand, p.size_value, p.size_unit, p.category, "
                    "       p.group_key, p.name_norm, COUNT(DISTINCT pr.store_id) AS store_count "
                    "FROM products p LEFT JOIN prices pr ON pr.product_id = p.id "
                    "GROUP BY p.id ORDER BY store_count DESC, p.name"
                ).fetchall()
                ballı = [
                    (match_score(r["name_norm"] or "", sorğu_tokenləri, allow_fuzzy=True), r)
                    for r in hamısı
                ]
                ballı = [(b, r) for b, r in ballı if b is not None]

            ballı.sort(key=lambda cüt: cüt[0])
            rows = [r for _, r in ballı]

        return {"items": [dict(r) for r in rows[:limit]]}
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
