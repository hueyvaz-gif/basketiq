"""
Bir kataloq faylını uçdan-uca yoxlayır: OCR -> təmizləmə -> nəticə.

    python tools/inspect_catalog.py data/sample_catalog.png
    python tools/inspect_catalog.py kataloq.pdf --psm 4
    python tools/inspect_catalog.py kataloq.pdf --raw     # xam mətni də göstər

Bu skript UI-dan asılı olmadan PSM rejimlərini müqayisə etmək üçündür.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.cleaner import clean_text  # noqa: E402
from ingestion.ocr import extract_text  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--psm", type=int, default=None, help="Tesseract PSM rejimi")
    parser.add_argument("--force-ocr", action="store_true", help="text layer-i yoxlama")
    parser.add_argument("--raw", action="store_true", help="xam mətni də çap et")
    args = parser.parse_args()

    if not args.path.exists():
        raise SystemExit(f"Fayl tapılmadı: {args.path}")

    result = extract_text(args.path, force_ocr=args.force_ocr, psm=args.psm)
    print(f"tip={result.source_type}  səhifə={result.pages}  "
          f"simvol={result.chars}  OCR={result.ocr_used}")
    for note in result.notes:
        print(f"  qeyd: {note}")

    if args.raw:
        print("=" * 70)
        print(result.text)

    cleaned = clean_text(result.text)
    print("=" * 70)
    print("STATS:", cleaned.stats)
    print("-" * 70)
    print(f"{'QIYMET':>8} | {'KOHNE':>8} | SETIR")
    print("-" * 70)
    for line in cleaned.lines:
        price = f"{line.price:.2f}" if line.price is not None else "-"
        old = f"{line.old_price:.2f}" if line.old_price is not None else "-"
        print(f"{price:>8} | {old:>8} | {line.text[:60]}")


if __name__ == "__main__":
    main()
