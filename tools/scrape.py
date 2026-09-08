"""
Scraper-i konsoldan işə salır.

İstifadə:
    python tools/scrape.py                      # mənbə siyahısı + robots yoxlaması
    python tools/scrape.py araz                 # Araz-dan 1 kataloq, ilk 3 səhifə
    python tools/scrape.py araz --pages 2
    python tools/scrape.py araz --files 3 --pages 4
    python tools/scrape.py araz --dry-run       # yalnız linkləri göstər, endirmə

Niyə ayrıca CLI? Serveri qaldırmadan mənbəni yoxlamaq üçün. Sayt quruluşunu
dəyişəndə ilk çağıracağın alət budur - `--dry-run` bir neçə saniyəyə deyir ki,
link hələ də tapılırmı.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows konsolu bəzən cp1252-dir - Azərbaycan hərfləri onu qırır
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ingestion.scraper import SOURCES, discover, robots_allows, scrape_source  # noqa: E402


def print_sources() -> None:
    print("\nMövcud mənbələr:\n")
    for source in SOURCES.values():
        allowed = robots_allows(source.page_url)
        mark = "✓" if allowed else "✗ QADAĞA"
        print(f"  {source.key:<6} {source.store:<14} robots: {mark}")
        print(f"         {source.page_url}")
        if source.note:
            print(f"         qeyd: {source.note}")
        print()
    print("İşə salmaq:  python tools/scrape.py <key>\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="BasketIQ kataloq scraper-i")
    ap.add_argument("source", nargs="?", help=f"mənbə açarı: {', '.join(sorted(SOURCES))}")
    ap.add_argument("--files", type=int, default=1, help="neçə kataloq faylı (default 1)")
    ap.add_argument("--pages", type=int, default=3, help="hər PDF-dən neçə səhifə (default 3)")
    ap.add_argument("--psm", type=int, default=0, help="Tesseract PSM (0 = .env defaultu)")
    ap.add_argument("--force-ocr", action="store_true", help="text layer-i yoxlama, birbaşa OCR")
    ap.add_argument("--selenium", action="store_true", help="statik yol boş qayıtsa brauzer aç")
    ap.add_argument("--dry-run", action="store_true", help="yalnız linkləri tap, endirmə")
    args = ap.parse_args()

    if not args.source:
        print_sources()
        return

    source = SOURCES.get(args.source)
    if source is None:
        print(f"Naməlum mənbə: '{args.source}'. Mövcud: {', '.join(sorted(SOURCES))}")
        raise SystemExit(1)

    print(f"\nMənbə: {source.store}  ({source.page_url})")

    if args.dry_run:
        links, used_selenium = discover(source, use_selenium=args.selenium)
        print(f"Tapılan link: {len(links)}   (selenium: {'bəli' if used_selenium else 'xeyr'})")
        for url in links:
            print(f"   • {url}")
        return

    print(f"Limit: {args.files} fayl × {args.pages} səhifə. OCR yavaşdır, gözlə...\n")
    report = scrape_source(
        key=args.source,
        max_files=args.files,
        max_pages=args.pages if args.pages > 0 else None,
        force_ocr=args.force_ocr,
        psm=args.psm if args.psm > 0 else None,
        use_selenium=args.selenium,
    )

    print(f"Tapılan link : {len(report.found)}")
    for url in report.found:
        print(f"   • {url}")

    print(f"\nEmal olundu  : {len(report.ingested)}")
    for item in report.ingested:
        print(
            f"   • kataloq #{item['catalog_id']}  {item['filename']}  "
            f"{item['size_mb']} MB  tip={item['source_type']}  "
            f"səhifə={item['pages']}  simvol={item['chars']}"
        )
        stats = item.get("stats") or {}
        print(f"     sətir: {stats.get('kept')} saxlanıldı / {stats.get('total_lines')} cəmi")
        for line in item.get("preview", [])[:5]:
            print(f"       {line.get('price')!s:>8}  {line.get('text', '')[:60]}")

    if report.skipped:
        print(f"\nÖtürüldü     : {len(report.skipped)}")
        for item in report.skipped:
            print(f"   • #{item['catalog_id']}  {item['reason']}")

    if report.errors:
        print(f"\nXəta         : {len(report.errors)}")
        for err in report.errors:
            print(f"   ✗ {err}")

    if report.ingested:
        cid = report.ingested[0]["catalog_id"]
        print("\nNövbəti addım: AI çıxarışı")
        print(f"   curl -X POST 'http://localhost:8000/api/catalogs/{cid}/extract?limit=10'")


if __name__ == "__main__":
    main()
