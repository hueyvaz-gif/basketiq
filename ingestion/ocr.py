"""
Kataloq faylından mətn çıxarma.

İki yol var və seçim AVTOMATİKDİR:
  1. PDF-in "text layer"-i varsa  -> pypdf (dəqiq, sürətli, səhvsiz)
  2. Skan PDF və ya şəkildirsə    -> pypdfium2 ilə şəkilə çevir -> pytesseract OCR

Niyə avtomatik seçim? OCR onlarla dəfə yavaşdır və hərf səhvləri edir.
Ondan yalnız başqa çarə olmayanda istifadə edirik. Bu, layihənin ən vacib
"ucuz yolu əvvəlcə sına" qərarıdır.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pypdfium2 as pdfium
import pytesseract
from PIL import Image, ImageOps

from app.config import settings
from ingestion.layout import parse_page
from ingestion.tess import configure_tesseract as _configure_tesseract

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
PDF_SUFFIXES = {".pdf"}
SUPPORTED_SUFFIXES = IMAGE_SUFFIXES | PDF_SUFFIXES


@dataclass
class ExtractionResult:
    """extract_text() nəticəsi - həm mətn, həm də hansı yolla alındığı."""

    text: str
    source_type: str          # 'pdf_text' | 'pdf_scan' | 'image'
    pages: int = 0
    ocr_used: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def chars(self) -> int:
        return len(self.text.strip())


# ---------------------------------------------------------------- yardımçılar


def file_sha256(path: Path) -> str:
    """Faylın barmaq izi. Eyni kataloqu iki dəfə emal etməmək üçün."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tess_config(psm: int) -> str:
    """--psm : səhifə seqmentasiya rejimi (6 = vahid mətn bloku, kataloq üçün yaxşı start)"""
    return f"--psm {psm}"


def _otsu_threshold(gray: Image.Image) -> int:
    """
    Şəkli ağ-qaraya çevirmək üçün ən uyğun həddi tapır (Otsu üsulu).

    Niyə sabit 128 yox? Kataloqların fonu rənglidir; sabit hədd ya mətni yeyir,
    ya fonu saxlayır. Otsu həddi hər şəkil üçün ayrıca hesablayır.
    """
    hist = gray.histogram()[:256]
    total = sum(hist)
    if total == 0:
        return 128

    sum_all = sum(i * hist[i] for i in range(256))
    sum_b = 0.0
    w_b = 0.0
    best_var, best_t = -1.0, 128

    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return best_t


def preprocess(img: Image.Image) -> Image.Image:
    """
    OCR-dan əvvəl şəkli hazırlayır: boz -> kontrast -> böyütmə -> ağ/qara.
    Xam kataloq şəklində OCR ~40-50% zibil verir, bu addımlardan sonra xeyli yaxşılaşır.
    """
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)

    # Kiçik şəkillərdə hərflər əzilir - böyüdürük
    if gray.width < 1600:
        factor = max(2, 1600 // max(gray.width, 1))
        gray = gray.resize(
            (gray.width * factor, gray.height * factor), Image.Resampling.LANCZOS
        )

    threshold = _otsu_threshold(gray)
    return gray.point(lambda p: 255 if p > threshold else 0, mode="1")


def page_text(img: Image.Image, psm: int | None = None, use_layout: bool = True) -> tuple[str, int]:
    """
    Bir səhifədən mətn: ƏVVƏLCƏ kart analizi, alınmasa adi OCR.

    Qaytarır: (mətn, tapılan kart sayı). Kart sayı 0-dırsa adi OCR işlədilib.

    Niyə iki yol? Qlyanslı kataloq kartlardan ibarətdir və adi OCR orada
    işləmir (ölçülüb: 0 məhsul). Amma sadə siyahı şəklindəki kataloqda kart
    yoxdur - orada adi OCR düzgün cavabdır. Səhifəyə baxıb qərar veririk.
    """
    # Layout analizi də Tesseract çağırır - yolu ondan ƏVVƏL göstərməliyik,
    # yoxsa TESSERACT_CMD lazım olan maşında bu yol susaraq uğursuz olar.
    _configure_tesseract()

    if use_layout:
        try:
            result = parse_page(img)
        except Exception:
            result = None
        if result is not None and len(result.cards) >= settings.layout_min_cards:
            return result.text, len(result.cards)

    return ocr_image(img, psm=psm), 0


def ocr_image(img: Image.Image, psm: int | None = None) -> str:
    _configure_tesseract()
    prepared = preprocess(img)
    return pytesseract.image_to_string(
        prepared,
        lang=settings.tesseract_langs,
        config=_tess_config(psm if psm is not None else settings.ocr_psm),
    )


# ---------------------------------------------------------------- PDF yolları


def pdf_text_layer(path: Path, max_pages: int) -> tuple[str, int]:
    """pypdf ilə mətni oxuyur. Skan PDF-də nəticə boş və ya çox qısa olur."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    total = len(reader.pages)
    parts = []
    for page in reader.pages[:max_pages]:
        parts.append(page.extract_text() or "")
    return "\n".join(parts), total


def pdf_pages_to_images(path: Path, max_pages: int, scale: float):
    """
    Skan PDF səhifələrini şəkilə çevirir (OCR üçün).
    scale=2.0 təxminən 144 DPI deməkdir - Tesseract üçün minimum məqbul keyfiyyət.
    """
    doc = pdfium.PdfDocument(str(path))
    try:
        for i in range(min(len(doc), max_pages)):
            yield doc[i].render(scale=scale).to_pil()
    finally:
        doc.close()


# ---------------------------------------------------------------- əsas funksiya


def extract_text(
    path: Path,
    force_ocr: bool = False,
    psm: int | None = None,
    max_pages: int | None = None,
    use_layout: bool | None = None,
) -> ExtractionResult:
    """
    Fayl -> mətn. Hansı yolun seçildiyini source_type ilə qaytarır ki,
    UI-da və DB-də görünsün (şəffaflıq: "bu mətn haradan gəldi?").

    max_pages: bu çağırış üçün səhifə limiti (None -> .env-dəki OCR_MAX_PAGES).
    Niyə lazımdır? Scraping ilə gələn kataloq 54 səhifə ola bilər; skan PDF-in
    hər səhifəsi ~10-20 saniyə OCR deməkdir. Sınaq zamanı 2-3 səhifə kifayətdir.
    """
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Dəstəklənməyən fayl tipi: {suffix}")

    max_pages = settings.ocr_max_pages if max_pages is None else max(1, max_pages)
    notes: list[str] = []

    use_layout = settings.layout_enabled if use_layout is None else use_layout

    # --- Şəkil ---
    if suffix in IMAGE_SUFFIXES:
        with Image.open(path) as img:
            text, cards = page_text(img, psm=psm, use_layout=use_layout)
        if cards:
            notes.append(f"Layout analizi: {cards} kart tapıldı")
        return ExtractionResult(
            text=text, source_type="image", pages=1, ocr_used=True, notes=notes
        )

    # --- PDF: əvvəlcə ucuz yol ---
    if not force_ocr:
        text, total_pages = pdf_text_layer(path, max_pages)
        if len(text.strip()) >= settings.pdf_text_min_chars:
            return ExtractionResult(
                text=text,
                source_type="pdf_text",
                pages=total_pages,
                ocr_used=False,
                notes=["Text layer tapıldı - OCR lazım olmadı"],
            )
        notes.append(
            f"Text layer zəifdir ({len(text.strip())} simvol) - OCR-a keçilir"
        )
    else:
        notes.append("force_ocr=True - text layer yoxlanmadı")
        total_pages = 0

    # --- PDF: skan yolu ---
    # Layout analizi daha böyük miqyas tələb edir (qiymət rəqəmləri kiçikdir).
    # Səhifəni İKİ DƏFƏ render etməmək üçün ən böyük miqyası seçirik.
    scale = max(settings.ocr_scale, settings.layout_scale) if use_layout else settings.ocr_scale
    pages_text = []
    page_count = 0
    total_cards = 0
    for img in pdf_pages_to_images(path, max_pages, scale):
        text, cards = page_text(img, psm=psm, use_layout=use_layout)
        pages_text.append(text)
        total_cards += cards
        page_count += 1
    if total_cards:
        notes.append(f"Layout analizi: {total_cards} kart tapıldı")
    if total_pages > max_pages:
        notes.append(f"Yalnız ilk {max_pages} səhifə emal olundu (cəmi {total_pages})")

    return ExtractionResult(
        text="\n".join(pages_text),
        source_type="pdf_scan",
        pages=total_pages or page_count,
        ocr_used=True,
        notes=notes,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("İstifadə: python -m ingestion.ocr <fayl>")
        raise SystemExit(1)

    result = extract_text(Path(sys.argv[1]))
    print(f"tip={result.source_type}  səhifə={result.pages}  simvol={result.chars}  OCR={result.ocr_used}")
    for n in result.notes:
        print(f"  qeyd: {n}")
    print("-" * 60)
    print(result.text[:1500])
