"""
Karantin növbəsi endpoint-ləri — nişanlanmış qiymət sətirləri (C12).

NİYƏ ADMİN TƏRƏFİNDƏDİR? Bu sətirlər istifadəçiyə QƏSDƏN göstərilmir:
şübhəli qiymət «bugünün endirimləri» siyahısına buraxılmır. Növbə isə
qərar verən üçündür — nə tutulub, hansı səbəbdən, yanlış-müsbətdirmi.
"""

from fastapi import APIRouter, HTTPException

from app.review import approve_price, flagged_prices

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/flagged")
def flagged(limit: int = 50):
    """Baxış gözləyən sətirlər + ümumi say (siyahı kəsilsə də rəqəm doğrudur)."""
    return flagged_prices(limit=limit)


@router.post("/flagged/{price_id}/approve")
def approve(price_id: int):
    """
    «Baxdım, qiymət realdır» — sətir karantindən çıxır və ekrana qayıdır.

    404 o deməkdir ki, sətir yoxdur VƏ YA onsuz da nişanlı deyil. İkisini
    ayırmırıq: hər iki halda görüləsi iş qalmır və admin siyahını yeniləyəndə
    həqiqi vəziyyəti görür.
    """
    if not approve_price(price_id):
        raise HTTPException(404, "nişanlı sətir tapılmadı")
    return {"ok": True, "price_id": price_id}
