"""
Tesseract-ın yerini və dil fayllarını göstərən tək nöqtə.

Niyə ayrıca fayl? Bu funksiyanı həm `ocr.py`, həm `layout.py` çağırır. Onu
`ocr.py`-də saxlasaydıq, `layout.py` `ocr.py`-dan import etməli olardı - amma
`ocr.py` da `layout.py`-dan import edir, yəni dairəvi asılılıq yaranardı.

Konfiqurasiya HƏR OCR çağırışından əvvəl edilir: funksiya ucuzdur (iki
dəyişən mənimsətməsi) və unudulma ehtimalını sıfıra endirir. Unudulsa,
Tesseract "not in your PATH" deyib qırılır - üstəlik yalnız o yolda.
"""

import os

import pytesseract

from app.config import settings


def configure_tesseract() -> None:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    if settings.tessdata_dir.exists():
        # Niyə --tessdata-dir yox, TESSDATA_PREFIX? pytesseract config sətrini
        # boşluqla parçalayır - qovluq adında boşluq varsa ("3nd month project")
        # --tessdata-dir yolu qırılır. Environment dəyişəni bu problemdən azaddır.
        os.environ["TESSDATA_PREFIX"] = str(settings.tessdata_dir)
