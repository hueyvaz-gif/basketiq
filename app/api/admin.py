"""
Admin panelinin VƏZİYYƏTİ (B11).

Bu, qapının ÖZÜ deyil - qapı `app/security.py`-dədir. Buradakı yeganə
endpoint brauzerə «panel açıqdırmı?» sualının cavabını verir ki, `nav.js`
bağlı halda tabı göstərməsin.

QƏSDƏN QORUNMAYIB: qapının arxasında olsaydı, bağlı vəziyyətdə özü də 404
verərdi və brauzer heç nə öyrənə bilməzdi. Cavab isə heç bir sirr açmır -
sayta baxan onsuz da tabın olub-olmadığını görür.
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
