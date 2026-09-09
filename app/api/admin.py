"""
Admin panelinin VƏZİYYƏTİ (B11).

Bu, qapının ÖZÜ deyil - qapı `app/security.py`-dədir. Buradakı yeganə
endpoint «admin səthi işləkdirmi?» sualına cavab verir.

P6-DAN SONRA İSTİFADƏÇİ İNTERFEYSİNDƏ ADMİN TABI YOXDUR (panel ayrıca
`/admin` ünvanındadır), yəni cavab artıq tab gizlətmək üçün lazım deyil.
Endpoint QALIR: xarici alət (n8n, monitorinq) «bu nüsxədə admin açıqdırmı?»
sualını soruşa bilər və `/admin` səhifəsinin özü onsuz da 404 verir.

QƏSDƏN QORUNMAYIB: qapının arxasında olsaydı, bağlı vəziyyətdə özü də 404
verərdi və soruşan heç nə öyrənə bilməzdi. Cavab isə sirr açmır.
"""

from fastapi import APIRouter, Depends

from app.config import settings
from app.coverage import store_coverage
from app.security import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/state")
def state():
    """`{"enabled": true|false}` — admin səthi işləyirmi."""
    return {"enabled": settings.admin_enabled}


@router.get("/coverage", dependencies=[Depends(require_admin)])
def coverage():
    """
    Market üzrə əhatə cədvəli (D15): məhsul sayı, qiymət sətri, son yenilənmə,
    əhatə faizi və mənbənin vəziyyəti.

    QAPININ ARXASINDADIR - yuxarıdakı `/state` endpoint-indən fərqli olaraq.
    Burada datanın nə qədər dolu olduğu, hansı mənbənin bağlı qaldığı yazılır;
    bu, saytın daxili vəziyyətidir və istifadəçiyə lazım deyil.
    """
    return store_coverage()
