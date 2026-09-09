"""
Məhsul şəkillərini konsoldan idarə edir.

    python tools/product_images.py                     # hesabat
    python tools/product_images.py fetch               # şəkli olmayanlara bax
    python tools/product_images.py fetch --limit 20
    python tools/product_images.py fetch --dry-run     # sorğu getmir, yalnız uyğunluq
    python tools/product_images.py pending             # manual baxış siyahısı
    python tools/product_images.py set 42 https://.../foto.png
    python tools/product_images.py reject 42 "səhv şəkil"

NİYƏ CLI, YALNIZ API YOX? Şəkil qərarı GÖZLƏ verilir: hesabatda ən aşağı
etibarlı sətirlərə baxıb «bu doğrudur, bu yox» demək lazımdır. Bunu terminaldan
etmək brauzerdə admin ekranı gəzməkdən sürətlidir - və server qalxmadan işləyir.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows konsolu bəzən cp1252-dir - Azərbaycan hərfləri onu qırır
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.services.product_images import (  # noqa: E402
    assign_images,
    coverage_report,
    reject_image,
    set_manual_image,
)


def print_report(worst: int) -> None:
    r = coverage_report(worst=worst)
    print(f"\nMəhsul (qiyməti olan) : {r['məhsul_cəmi']}")
    print(f"Şəkilli               : {r['şəkilli']}  ({r['əhatə_faizi']}%)")
    print(f"Rədd edilən           : {r['rədd']}")
    print(f"Uğursuz (sayt/şəbəkə) : {r['uğursuz']}")
    print(f"Orta etibar           : {r['orta_etibar']}")

    if r["ən_zəif"]:
        print(f"\nƏn aşağı etibarlı {len(r['ən_zəif'])} şəkil - səhv axtarmağa buradan başla:")
        for s in r["ən_zəif"]:
            ad = f"{s['brand'] or ''} {s['name']}".strip()
            print(f"   {s['confidence']:.2f}  #{s['product_id']:<5} {ad[:42]:<42} {s['source_url']}")
    print()


def print_pending(limit: int) -> None:
    r = coverage_report(worst=0)
    siyahı = r["manual_baxış"][:limit]
    print(f"\nManual baxış siyahısı ({len(siyahı)} / {r['rədd']}):\n")
    for s in siyahı:
        print(f"   #{s['product_id']:<5} {s['name'][:40]:<40} bal={s['confidence']:.2f}  {s['note']}")
    print("\nƏl ilə təyin:  python tools/product_images.py set <id> <şəkil ünvanı>\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="BasketIQ məhsul şəkilləri")
    sub = ap.add_subparsers(dest="cmd")

    p_fetch = sub.add_parser("fetch", help="şəkli olmayan məhsullara şəkil axtar")
    p_fetch.add_argument("--limit", type=int, default=None)
    p_fetch.add_argument("--dry-run", action="store_true")

    p_pending = sub.add_parser("pending", help="manual baxış siyahısı")
    p_pending.add_argument("--limit", type=int, default=30)

    p_set = sub.add_parser("set", help="şəkli əl ilə təyin et")
    p_set.add_argument("product_id", type=int)
    p_set.add_argument("url")

    p_reject = sub.add_parser("reject", help="şəkli rədd et (avtomatika bir daha təyin etməyəcək)")
    p_reject.add_argument("product_id", type=int)
    p_reject.add_argument("note", nargs="?", default="əl ilə rədd edildi")

    ap.add_argument("--worst", type=int, default=20, help="hesabatda neçə zəif sətir")
    args = ap.parse_args()

    if args.cmd == "fetch":
        h = assign_images(limit=args.limit, dry_run=args.dry_run)
        manual = h.pop("manual_siyahı", [])
        print(f"\nBaxılan: {h['baxılan']}   şəkilləndi: {h['ok']}   "
              f"rədd: {h['rejected']}   uğursuz: {h['failed']}")
        if h.get("xəta"):
            print(f"XƏTA: {h['xəta']}")
        print(f"Manual baxış siyahısına düşən: {len(manual)}\n")
        print_report(args.worst)
    elif args.cmd == "pending":
        print_pending(args.limit)
    elif args.cmd == "set":
        ok = set_manual_image(args.product_id, args.url)
        print("Təyin edildi." if ok else "Alınmadı: şəkil endirilmədi və ya yararsızdır.")
    elif args.cmd == "reject":
        reject_image(args.product_id, args.note)
        print(f"#{args.product_id} rədd edildi.")
    else:
        print_report(args.worst)


if __name__ == "__main__":
    main()
