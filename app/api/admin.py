"""
Admin panelinin VƏZİYYƏTİ (B11).

Bu, qapının ÖZÜ deyil - qapı `app/security.py`-dədir. Buradakı yeganə
endpoint brauzerə «panel açıqdırmı?» sualının cavabını verir ki, `nav.js`
bağlı halda tabı göstərməsin.

QƏSDƏN QORUNMAYIB: qapının arxasında olsaydı, bağlı vəziyyətdə özü də 404
verərdi və brauzer heç nə öyrənə bilməzdi. Cavab isə heç bir sirr açmır -
sayta baxan onsuz da tabın olub-olmadığını görür.
"""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/state")
def state():
    """`{"enabled": true|false}` — admin səthi işləyirmi."""
    return {"enabled": settings.admin_enabled}
