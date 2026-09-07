"""
Matching süzgəcinin statistikası: neçə cütdən neçəsi LLM-ə gedir?

    python tools/match_stats.py            # hazırkı vəziyyət
    python tools/match_stats.py --reset    # matching sıfırlanmış kimi ölçür

NİYƏ BU ALƏT VAR?
README-də "78 mümkün cütdən yalnız 4-ü LLM-ə buraxdı" yazılıb. Bu rəqəm
matching İŞƏ DÜŞMƏZDƏN ƏVVƏL ölçülüb - sonra hər şey qruplaşdığı üçün
`/api/match/candidates` 0 qaytarır və rəqəmi təkrarlamaq mümkün olmur.
Sənəddə yoxlana bilməyən rəqəm saxlamaq düzgün deyil, ona görə alət yazıldı.

`--reset` NECƏ TƏHLÜKƏSİZDİR?
Sıfırlama yalnız ölçmə müddətində qalır: `group_key` əvvəlcə fayla yazılır,
sonra `finally` blokunda MÜTLƏQ bərpa olunur. Skript qırılsa belə, ehtiyat
nüsxə diskdə qalır və `--restore` ilə geri qaytarıla bilər.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai.matcher import (  # noqa: E402
    MIN_SIMILARITY,
    find_candidates,
    key_parts,
    load_products,
    similarity,
)
from app.config import settings  # noqa: E402
from app.db import db_cursor, get_connection  # noqa: E402

BACKUP = settings.data_dir / "group_key_backup.json"


def snapshot() -> list[dict]:
    conn = get_connection()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT id, canonical_key, group_key FROM products ORDER BY id"
            )
        ]
    finally:
        conn.close()


def restore(rows: list[dict]) -> None:
    with db_cursor() as cur:
        for row in rows:
            cur.execute(
                "UPDATE products SET group_key = ? WHERE id = ?",
                (row["group_key"], row["id"]),
            )


def stage_counts(products: list[dict]) -> dict:
    """Süzgəcin hər pilləsində neçə cüt atılır - `find_candidates` ilə eyni şərtlər."""
    counts = {"total": 0, "size_conflict": 0, "same_group": 0, "low_similarity": 0,
              "passed": 0}

    for i, a in enumerate(products):
        _, size_a = key_parts(a["canonical_key"])
        for b in products[i + 1:]:
            counts["total"] += 1
            _, size_b = key_parts(b["canonical_key"])

            if size_a and size_b and size_a != size_b:
                counts["size_conflict"] += 1
                continue
            if a.get("group_key") and a["group_key"] == b.get("group_key"):
                counts["same_group"] += 1
                continue
            if similarity(a["canonical_key"], b["canonical_key"]) < MIN_SIMILARITY:
                counts["low_similarity"] += 1
                continue
            counts["passed"] += 1

    return counts


def report() -> None:
    products = load_products()
    if not products:
        print("Bazada məhsul yoxdur.")
        return

    counts = stage_counts(products)
    candidates = find_candidates(products)

    print(f"  Məhsul sayı            : {len(products)}")
    print(f"  Mümkün cüt (C(n,2))    : {counts['total']}")
    print(f"  - ölçü ziddiyyəti      : -{counts['size_conflict']}")
    print(f"  - artıq eyni qrupda    : -{counts['same_group']}")
    print(f"  - oxşarlıq həddi altı  : -{counts['low_similarity']}  (hədd {MIN_SIMILARITY})")
    print(f"  = LLM-ə gedən          : {counts['passed']}")

    if counts["total"]:
        saved = 100 * (1 - counts["passed"] / counts["total"])
        print(f"  Süzülmə                : {saved:.1f}%")

    if candidates:
        print("\n  LLM-ə gedəcək cütlər:")
        for c in candidates:
            print(f"    {c.similarity:.3f}  «{c.a_text}»  ≟  «{c.b_text}»")


def main() -> None:
    ap = argparse.ArgumentParser(description="Matching süzgəcinin statistikası")
    ap.add_argument("--reset", action="store_true",
                    help="matching sıfırlanmış kimi ölç (sonra avtomatik bərpa olunur)")
    ap.add_argument("--restore", action="store_true",
                    help="ehtiyat nüsxədən group_key-i bərpa et")
    args = ap.parse_args()

    if args.restore:
        if not BACKUP.exists():
            print(f"Ehtiyat nüsxə yoxdur: {BACKUP}")
            raise SystemExit(1)
        rows = json.loads(BACKUP.read_text(encoding="utf-8"))
        restore(rows)
        print(f"Bərpa olundu: {len(rows)} məhsul")
        return

    if not args.reset:
        print("\n=== HAZIRKI VƏZİYYƏT ===")
        report()
        print("\n(Matching artıq işləyibsə 'LLM-ə gedən' 0 olacaq - "
              "ilkin rəqəmi görmək üçün: --reset)")
        return

    before = snapshot()
    settings.ensure_dirs()
    BACKUP.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Ehtiyat nüsxə: {BACKUP}")
    print(f"Əvvəl: {len(before)} məhsul, {len({r['group_key'] for r in before})} qrup")

    try:
        with db_cursor() as cur:
            cur.execute("UPDATE products SET group_key = canonical_key")
        print("\n=== SIFIRLANMIŞ VƏZİYYƏT ===")
        report()
    finally:
        restore(before)
        after = snapshot()
        ok = all(a["group_key"] == b["group_key"] for a, b in zip(before, after))
        print(f"\nBərpa: {'✓ tamamlandı' if ok else '✗ UYĞUNSUZLUQ - --restore işlət!'}")
        print(f"Qrup sayı: {len({r['group_key'] for r in after})}")


if __name__ == "__main__":
    main()
