"""Analitika endpoint-ləri: qiymət tarixçəsi və endirim yoxlaması."""

from fastapi import APIRouter, HTTPException

from app.analytics import discount_summary, price_history, tracked_groups

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/groups")
def groups(limit: int = 30):
    """Qrafik üçün məhsul siyahısı - ən çox müşahidəsi olanlar əvvəldə."""
    return {"items": tracked_groups(limit=limit)}


@router.get("/history")
def history(group_key: str, limit: int = 100):
    """Bir məhsul qrupunun qiymət tarixçəsi (qrafikin datası)."""
    if not group_key.strip():
        raise HTTPException(400, "group_key boş ola bilməz")
    return price_history(group_key.strip(), limit=limit)


@router.get("/discounts")
def discounts(limit: int = 50):
    """
    Elan olunan endirimlərin yoxlanması.

    Hökm dördlüdür: təsdiqlənib / təsdiqlənməyib / şübhəli / endirim yoxdur.
    "Təsdiqlənməyib" ayrıca hal kimi saxlanılır - tarixçəsi olmayan məhsulun
    iddiasını nə təsdiqləmək, nə də təkzib etmək mümkündür.
    """
    return discount_summary(limit=limit)
