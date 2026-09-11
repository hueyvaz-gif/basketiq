"""
UYĞUNLAŞDIRMANI GERİ QAYTARMAQ (ADDIM 4).

    python -m tools.match_rollback --save data/group_key_backup.json   # indiki vəziyyəti saxla
    python -m tools.match_rollback --backup FAYL                       # nə dəyişəcəyini göstər
    python -m tools.match_rollback --backup FAYL --yes                 # geri qaytar
    python -m tools.match_rollback --backup FAYL --yes --drop-match-key

NƏ GERİ QAYIDIR?
  1. `products.group_key` — ehtiyat faylındakı vəziyyətə. Ehtiyatdan SONRA
     yaranmış məhsullar (yeni çəkiliş) öz canonical_key-ini alır: onlar o vaxt
     heç bir qrupda deyildi.
  2. `match_decisions` cədvəli silinir (bütün avtomatik, LLM və İNSAN qərarları).
  3. `--drop-match-key` ilə `products.match_key` sütunu da silinir.

NİYƏ SÜTUN SUSMAYA GÖRƏ SİLİNMİR? Onu heç bir köhnə sorğu oxumur, yəni
zərərsizdir; silmək isə növbəti server başlanğıcında `_migrate` tərəfindən
yenidən yaradılacaq (sxem kodu hələ də onu tələb edir). Tam geri qaytarma
= bu alət + `git revert` (kod da geri getməlidir).

NİYƏ SUSMAYA GÖRƏ YALNIZ GÖSTƏRİR? İnsan qərarları da silinir və onlar
ehtiyatda YOXDUR — təsadüfən işə salınan alət admin panelində saatlarla
görülən işi yox edərdi. `--yes` şüurlu addımdır.

`tools/match_stats.py --restore` ilə fərqi: o, yalnız group_key-i bərpa edir
və tək bir sabit faylı oxuyur. Bu alət istənilən ehtiyatı qəbul edir və
uyğunlaşdırmanın bütün izini təmizləyir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.db import get_connection  # noqa: E402


def save(path: Path) -> int:
    """İndiki group_key vəziyyətini fayla yazır: [{id, canonical_key, group_key}]."""
    conn = get_connection()
    try:
        rows = [
            dict(r)
            for r in conn.execute("SELECT id, canonical_key, group_key FROM products ORDER BY id")
        ]
    finally:
        conn.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


def plan(conn, backup: list[dict]) -> dict:
    """Nə dəyişəcək — bazaya toxunmadan."""
    saved = {r["id"]: r["group_key"] for r in backup}
    current = conn.execute("SELECT id, canonical_key, group_key FROM products").fetchall()
    changes = []
    for row in current:
        target = saved.get(row["id"], row["canonical_key"])
        if row["group_key"] != target:
            changes.append((target, row["id"]))

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    decisions = (
        conn.execute("SELECT source, COUNT(*) FROM match_decisions GROUP BY source").fetchall()
        if "match_decisions" in tables
        else []
    )
    columns = {r[1] for r in conn.execute("PRAGMA table_info(products)")}
    return {
        "changes": changes,
        "new_since_backup": sum(1 for r in current if r["id"] not in saved),
        "decisions": {r[0]: r[1] for r in decisions},
        "has_decisions_table": "match_decisions" in tables,
        "has_match_key": "match_key" in columns,
    }


def rollback(conn, backup: list[dict], drop_match_key: bool) -> dict:
    """Bir tranzaksiyada geri qaytarır. Xəta olsa heç nə dəyişmir."""
    info = plan(conn, backup)
    with conn:
        conn.executemany("UPDATE products SET group_key = ? WHERE id = ?", info["changes"])
        conn.execute("DROP TABLE IF EXISTS match_decisions")
        if drop_match_key and info["has_match_key"]:
            conn.execute("DROP INDEX IF EXISTS idx_products_match_key")
            conn.execute("ALTER TABLE products DROP COLUMN match_key")
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="Uyğunlaşdırmanı geri qaytar")
    ap.add_argument("--save", type=Path, help="indiki group_key vəziyyətini bu fayla yaz")
    ap.add_argument("--backup", type=Path, help="bərpa ediləcək ehtiyat faylı")
    ap.add_argument("--yes", action="store_true", help="həqiqətən icra et (əks halda yalnız göstərir)")
    ap.add_argument("--drop-match-key", action="store_true", help="products.match_key sütununu da sil")
    args = ap.parse_args()

    if args.save:
        print(f"saxlanıldı: {args.save} ({save(args.save)} məhsul)")
        return 0

    if not args.backup:
        ap.error("--save və ya --backup lazımdır")
    if not args.backup.exists():
        print(f"ehtiyat faylı yoxdur: {args.backup}")
        return 1

    backup = json.loads(args.backup.read_text(encoding="utf-8"))
    conn = get_connection()
    try:
        info = rollback(conn, backup, args.drop_match_key) if args.yes else plan(conn, backup)
    finally:
        conn.close()

    verb = "DƏYİŞDİ" if args.yes else "dəyişəcək"
    print(f"group_key {verb}: {len(info['changes'])} məhsul "
          f"(ehtiyatdan sonra yaranan: {info['new_since_backup']})")
    if info["has_decisions_table"]:
        print(f"match_decisions {'silindi' if args.yes else 'silinəcək'}: {info['decisions'] or 'boş'}")
        if info["decisions"].get("human"):
            print("  DİQQƏT: insan qərarları ehtiyatda YOXDUR — geri gəlməyəcək.")
    if args.drop_match_key and info["has_match_key"]:
        print(f"products.match_key {'silindi' if args.yes else 'silinəcək'} "
              "(növbəti server başlanğıcı onu yenidən yaradacaq - kodu da geri qaytar)")
    if not args.yes:
        print("\nHeç nə dəyişmədi. İcra etmək üçün: --yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
