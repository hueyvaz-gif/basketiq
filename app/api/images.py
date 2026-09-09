"""
Məhsul şəkilləri: gündəlik çəkiliş, hesabat və əl ilə düzəliş.

NİYƏ AYRICA ROUTER? Şəkil çəkilişi kataloq çəkilişindən FƏRQLİ mənbədən
(market saytının məhsul səhifələrindən) və FƏRQLİ ritmlə işləyir - kataloq
həftədə bir dəyişir, şəkil isə bir dəfə tapılandan sonra aylarla eynidir.
Onları bir endpoint-də birləşdirmək «yalnız kataloq çək» halını mümkünsüz
edərdi.

ZƏNCİRDƏ YERİ: n8n gündəlik axını kataloqu çəkir → AI məhsulları çıxarır →
BURASI yeni məhsullara şəkil axtarır. Ardıcıllıq məcburidir: şəkil məhsulun
adı bazada olandan sonra axtarıla bilər.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.api.scrape import check_api_key
from app.security import require_admin
from app.services.product_images import (
    assign_images,
    coverage_report,
    reject_image,
    set_manual_image,
)

router = APIRouter(prefix="/api/images", tags=["images"], dependencies=[Depends(require_admin)])


class ManualImageIn(BaseModel):
    source_url: str


@router.get("/report")
def report(worst: int = 20):
    """«Neçə məhsulda şəkil var və ən şübhəliləri hansılardır?»"""
    return coverage_report(worst=worst)


@router.post("/refresh")
def refresh(limit: int | None = None, dry_run: bool = False,
            x_api_key: str | None = Header(default=None)):
    """
    Şəkli olmayan (və ya vaxtı çatmış) məhsullara şəkil axtarır.

    LİMİT VAR, çünki bu, kənar sayta sorğu deməkdir: nəzakət gecikməsi ilə
    hər məhsul ~2 saniyədir. n8n gündəlik zəncirdə kiçik limitlə çağırır -
    yeni məhsullar bir neçə günə tədricən şəkillənir və sayt heç vaxt
    bizim üzümüzdən yüklənmir.
    """
    check_api_key(x_api_key)
    hesabat = assign_images(limit=limit, dry_run=dry_run)
    # Manual siyahı uzundur (rədd edilən hər məhsul) - cavabda YALNIZ sayı
    # qalır, tam siyahı `GET /report`-dadır.
    hesabat["manual_baxış_sayı"] = len(hesabat.pop("manual_siyahı", []))
    return hesabat


@router.post("/{product_id}/manual")
def manual(product_id: int, body: ManualImageIn,
           x_api_key: str | None = Header(default=None)):
    """
    Şəkli əl ilə təyin edir. AVTOMATİKA BUNUN ÜSTÜNDƏN YAZMIR.

    Ünvan yenə də yoxlanılır və endirilir: «əl ilə» kənar fayla gözübağlı
    inanmaq demək deyil.
    """
    check_api_key(x_api_key)
    if not set_manual_image(product_id, body.source_url):
        raise HTTPException(400, "Şəkil endirilmədi və ya yararsızdır")
    return {"ok": True, "product_id": product_id}


@router.post("/{product_id}/reject")
def reject(product_id: int, note: str = "əl ilə rədd edildi",
           x_api_key: str | None = Header(default=None)):
    """Səhv şəkli silir və avtomatikanın onu bir daha təyin etməsini dayandırır."""
    check_api_key(x_api_key)
    reject_image(product_id, note)
    return {"ok": True, "product_id": product_id}
