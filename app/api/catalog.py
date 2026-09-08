"""
Kataloq endpoint-ləri: bugünün endirimləri, məhsul səhifəsi, AI qeydi.

NİYƏ AI QEYDİ AYRICA ENDPOINT-DİR?
Məhsul səhifəsinin datası (`/product/{id}`) bazadan millisaniyələrlə gəlir,
AI qeydi isə modeldən saniyələrlə. Bir cavabda birləşdirsək, bütün səhifə
ən yavaş hissəni gözləyərdi. İki çağırış: cədvəl dərhal görünür, qeyd
hazır olanda öz yerinə düşür. Model əlçatmaz olsa, qeyd sadəcə gəlmir —
səhifə isə tam işləkdir.
"""

from fastapi import APIRouter, HTTPException

from ai.product_note import product_note
from app.catalog import product_detail, search, store_page, todays_deals
from app.stores import market_status

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/markets")
def markets():
    """
    Dörd marketin siyahısı və hər birinin datası varmı.

    `available=False` olan market UI-dan SİLİNMİR — «Tezliklə» kimi
    işarələnir. Beləliklə istifadəçi «niyə cəmi iki market?» sualının
    cavabını görür.
    """
    return {"items": market_status()}


@router.get("/deals")
def deals(limit: int = 12):
    """«Bugünün ən sərfəli endirimləri» — hər məhsul üçün ən böyük faiz."""
    limit = max(1, min(limit, 60))
    return todays_deals(limit=limit)


@router.get("/search")
def catalog_search(
    q: str = "",
    market: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 48,
):
    """
    Axtarış / kateqoriya səhifəsinin datası: şəkilli kartlar + filtr menyusu.

    Bütün parametrlər isteğe bağlıdır - heç biri verilməsə bütün kataloq
    qayıdır (limit çərçivəsində).
    """
    limit = max(1, min(limit, 200))
    return search(
        q=q,
        market=market,
        category=category,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
    )


@router.get("/store/{slug}")
def store(slug: str, limit: int = 40):
    """
    Bir marketin səhifəsi: endirimləri + məhsulları.

    Reyestrdə olmayan slug 404 verir — uydurma market səhifəsi açılmır.
    Reyestrdə olan, amma datası hələ olmayan market isə 200 qaytarır və boş
    siyahı ilə gəlir: səhifə vəziyyəti izah edir.
    """
    limit = max(1, min(limit, 200))
    data = store_page(slug, limit=limit)
    if data is None:
        raise HTTPException(404, "Market tapılmadı")
    return data


@router.get("/product/{product_id}")
def product(product_id: int):
    """Məhsul səhifəsinin bütün datası — AI qeydindən başqa."""
    detail = product_detail(product_id)
    if detail is None:
        raise HTTPException(404, "Məhsul tapılmadı")
    detail["markets"] = market_status()
    return detail


@router.get("/product/{product_id}/note")
def note(product_id: int):
    """
    Məhsul üçün AI qeydi (trolley-dəki «rəylər» bölməsinin əvəzi).

    Qeyd UYDURMA RƏY DEYİL: model yalnız hesablanmış qiymət faktlarını
    cümləyə çevirir. Yoxlamalardan biri düşsə, cavab `available: false`
    olur və səhifə həmin bölməni ümumiyyətlə göstərmir.
    """
    detail = product_detail(product_id)
    if detail is None:
        raise HTTPException(404, "Məhsul tapılmadı")

    result = product_note(detail)
    # `facts` qaytarılır ki, istifadəçi «modelə nə göndərildi?» sualına cavab
    # tapa bilsin - eyni şəffaflıq səbət tövsiyəsində də var.
    return {
        "available": result["available"],
        "text": result["text"],
        "cached": result["cached"],
        "facts": result["facts"],
        "check": result["check"],
    }
