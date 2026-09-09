"""
ADMİN QAPISI (B11) — panelin istehsalda bağlanması.

NƏ QORUNUR? Admin səthi datanı DƏYİŞİR: kataloq yükləyir, mənbədən çəkir,
kataloq silir, karantin qərarı verir. İstifadəçi səthi isə yalnız oxuyur.
İkisi eyni sayta baxdığı üçün fərq görünmür - ünvanı bilən hər kəs yazan
endpoint-ə çata bilir.

QAPI SADƏDİR, ÇÜNKİ LAYİHƏDƏ HESAB YOXDUR. Parol sistemi qurmaq bu
tapşırığın hüdudundan kənardır və yarımçıq qurulmuş autentifikasiya
qapısızlıqdan da pisdir: təhlükəsizlik hissi verir, təhlükəsizlik vermir.
Ona görə qapı mühit dəyişənidir (`ADMIN_ENABLED`) - yəni qərar serveri
qaldıran adamındır, brauzerdən dəyişdirilə bilmir.

NİYƏ 404, 403 YOX? Bağlı panel «icazən yoxdur» deyil, «burada belə səhifə
yoxdur» deməkdir. 403 endpoint-in MÖVCUD olduğunu təsdiqləyir və axtaran
adama xəritə verir; 404 heç nə demir.

FRONTEND QORUMA DEYİL. `nav.js` tabı gizlədir, amma statik HTML onsuz da
brauzerə gedir - gizlətmək yalnız səliqədir. Əsl qapı buradadır, serverdə.
"""

from fastapi import HTTPException

from app.config import settings


def require_admin() -> None:
    """
    Admin endpoint-ləri üçün asılılıq. Panel bağlıdırsa 404 atır.

    Ayrıca funksiya olması qəsdəndir: qapının açılma şərti tək yerdədir və
    dəyişəndə bütün endpoint-lər ardınca dəyişir.
    """
    if not settings.admin_enabled:
        raise HTTPException(404, "tapılmadı")
