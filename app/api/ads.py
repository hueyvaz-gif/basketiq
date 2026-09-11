"""
REKLAM endpoint-ləri (E19-E24) — iki ayrı səth.

İCTİMAİ (`/api/ads`): səhifə slotu soruşur, klik sayılır. Qapı yoxdur -
reklam onsuz da hər ziyarətçiyə göstərilir.

ADMİN (`/api/admin/ads`): sifarişin yaradılması, redaktəsi, silinməsi və
hesabat rəqəmləri. Qapının arxasındadır (`app/security.py`), çünki bu, saytın
inventarını dəyişən əməliyyatdır.

NİYƏ İKİ ROUTER, BİR PREFİKS YOX? Eyni prefiksdə qarışsaydılar, qapı ya
hamısını bağlayardı (səhifə reklamı görməzdi), ya heç birini (hər kəs sifariş
yarada bilərdi). Ayrı prefiks fərqi ünvanın özündə görünən edir.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.ads import (
    SLOTS,
    create_ad,
    current_ad,
    delete_ad,
    list_ads,
    record_click,
    record_impression,
    rendered_slots,
    update_ad,
)
from app.config import settings
from app.security import require_admin

router = APIRouter(prefix="/api/ads", tags=["ads"])
admin_router = APIRouter(
    prefix="/api/admin/ads", tags=["ads-admin"], dependencies=[Depends(require_admin)]
)

# Kreativ üçün icazəli fayl tipləri.
#
# SVG QƏSDƏN YOXDUR: SVG icra oluna bilən sənəddir (skript daşıya bilər) və
# eyni origin-dən verilsə, brauzer onu bizim səhifəmizin hüquqları ilə
# oxuyar. Repodakı nümunə banner SVG-dir, amma onu biz yazmışıq - yüklənən
# fayl isə kənardan gəlir.
CREATIVE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
CREATIVE_MAX_BYTES = 2 * 1024 * 1024
# Media qovluğundadır (`settings.media_dir`): Docker-də bazanın volume-u -
# yeniləmədə itmir. URL köhnədir, `/static` mount-u oranı da görür.
CREATIVE_DIR = settings.media_dir / "images" / "ads"
CREATIVE_URL = "/static/images/ads"


# ------------------------------------------------------------------ ictimai


@router.get("/slot/{slot}")
def slot_ad(slot: str):
    """
    Slotda göstəriləcək reklam. Sifariş yoxdursa `ad: null` - UI həmin halda
    «Sizin reklamınız burada ola bilər» yazır (E20), yəni boş yer gizlənmir.

    GÖSTƏRİM BURADA SAYILIR. Dürüst adı «göstərilmək üçün göndərildi»dir:
    istifadəçinin ekranında həqiqətən görünüb-görünmədiyini server bilə bilməz.
    """
    if slot not in SLOTS:
        raise HTTPException(404, f"Naməlum slot: '{slot}'")

    ad = current_ad(slot)
    if ad:
        record_impression(ad["id"])
    # `contact` boş slotun CTA-sı üçündür (E20). Ünvan konfiqurasiyadadır -
    # kodda uydurma e-poçt saxlamırıq.
    return {"slot": slot, "ad": ad, "contact": settings.ads_contact}


@router.get("/{ad_id}/click")
def click(ad_id: int):
    """
    Kliki sayır və reklamverənin ünvanına yönləndirir.

    NİYƏ YÖNLƏNDİRMƏ, JS SAYĞACI YOX? Keçid adi `<a href>`-dir: JS sönük olsa
    da, reklam işləyir və klik yenə sayılır. Sayğac JS-ə bağlansaydı,
    reklamverənin hesabatı istifadəçinin brauzer ayarından asılı olardı.
    """
    hədəf = record_click(ad_id)
    if not hədəf:
        raise HTTPException(404, "reklam tapılmadı")
    # Yalnız veb ünvanına yönləndiririk: `javascript:` və `data:` sxemləri
    # bazaya düşsəydi, klik keçidi skript icrasına çevrilərdi.
    if not hədəf.startswith(("http://", "https://")):
        raise HTTPException(400, "hədəf ünvan düzgün deyil")
    return RedirectResponse(hədəf, status_code=307)


# -------------------------------------------------------------------- admin


class AdIn(BaseModel):
    """Yeni sifariş. Tarixlər `YYYY-MM-DD` formatındadır."""

    advertiser: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    target_url: str = Field(min_length=1, max_length=500)
    slot: str
    starts_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    ends_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    body: str = Field(default="", max_length=400)
    image_path: str | None = None
    active: bool = True


class AdPatch(BaseModel):
    """Redaktə: yalnız göndərilən sahələr dəyişir."""

    advertiser: str | None = None
    title: str | None = None
    target_url: str | None = None
    slot: str | None = None
    starts_at: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    ends_at: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    body: str | None = None
    image_path: str | None = None
    active: bool | None = None


def _require_rendered(slot: str) -> None:
    """
    Reyestrdə olan, amma HEÇ BİR səhifədə çəkilməyən slota yazmağı rədd edir.

    Forma onu onsuz da təklif etmir; bu, API səviyyəsində ikinci qapıdır -
    əl ilə göndərilən sorğu da görünməz reklam yarada bilməsin. Naməlum slotu
    isə `create_ad`/`update_ad` özü rədd edir (reyestr yoxlaması).
    """
    if slot in SLOTS and slot not in rendered_slots():
        raise HTTPException(
            400,
            f"«{SLOTS[slot]}» hazırda heç bir səhifədə göstərilmir - "
            "bu yerə yazılan reklam görünməz olardı.",
        )


@admin_router.get("")
def all_ads():
    """
    Bütün sifarişlər + formanın seçim siyahısı.

    Seçim siyahısında YALNIZ səhifədə çəkilən slotlar var (`rendered_slots`).
    Başqa slotdakı köhnə sifariş itmir: `on_page: false` ilə gəlir və admin
    cədvəlində «niyə görünmür?» sualının cavabı elə orada yazılır.
    """
    görünən = rendered_slots()
    items = [{**ad, "on_page": ad["slot"] in görünən} for ad in list_ads()]
    slots = [{"key": k, "label": v} for k, v in SLOTS.items() if k in görünən]
    return {"items": items, "slots": slots}


@admin_router.post("")
def add_ad(payload: AdIn):
    _require_rendered(payload.slot)
    try:
        ad_id = create_ad(**payload.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": ad_id}


@admin_router.patch("/{ad_id}")
def edit_ad(ad_id: int, payload: AdPatch):
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    # Yalnız slot DƏYİŞƏNDƏ yoxlanır: görünməyən slotdakı köhnə sifarişi
    # dayandırmaq və ya tarixini dəyişmək hələ də mümkün olmalıdır.
    if "slot" in fields:
        _require_rendered(fields["slot"])
    try:
        if not update_ad(ad_id, **fields):
            raise HTTPException(404, "reklam tapılmadı")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@admin_router.delete("/{ad_id}")
def remove_ad(ad_id: int):
    if not delete_ad(ad_id):
        raise HTTPException(404, "reklam tapılmadı")
    return {"ok": True}


@admin_router.post("/creative")
async def upload_creative(file: UploadFile = File(...)):
    """
    Kreativ şəkli yükləyir və ünvanını qaytarır.

    Fayl media qovluğunun `images/ads/` altına düşür (lokalda
    `app/static/images/ads/`, Docker-də `/data/media/images/ads/`) - məhsul
    şəkilləri ilə eyni məntiq. Ad TƏSADÜFİ verilir: yüklənən adı saxlasaydıq, eyni adlı ikinci
    fayl birincini əvəz edər və işləyən reklamın şəkli səssizcə dəyişərdi.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in CREATIVE_SUFFIXES:
        raise HTTPException(
            400, f"İcazəli tiplər: {', '.join(sorted(CREATIVE_SUFFIXES))}"
        )

    content = await file.read()
    if len(content) > CREATIVE_MAX_BYTES:
        raise HTTPException(400, "Fayl 2 MB-dan böyükdür")
    if not content:
        raise HTTPException(400, "Fayl boşdur")

    CREATIVE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    (CREATIVE_DIR / name).write_bytes(content)
    return {"path": f"{CREATIVE_URL}/{name}", "bytes": len(content)}
