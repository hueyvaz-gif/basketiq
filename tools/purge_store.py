"""
Reyestrdən kənar marketi bazadan TAMAMİLƏ silir.

    python -m tools.purge_store kohne-market            # nə silinəcəyini göstərir
    python -m tools.purge_store kohne-market --apply    # həqiqətən silir

NİYƏ SCRIPT, ƏL İLƏ SQL DEYİL?
Silinmə geri dönməzdir və bir neçə cədvələ toxunur (`prices`, `catalogs`,
`price_snapshots`, `basket_items`, `products`). Əl ilə yazılan SQL-də bir
cədvəli unutmaq həm xarici açar səhvi verir, həm də bazada asılı qalmış
sətirlər buraxır. Script həmişə eyni ardıcıllığı işlədir və əvvəlcə NƏ
silinəcəyini göstərir.

YETİM MƏHSUL NƏDİR?
`products` cədvəli marketdən asılı deyil - eyni məhsul bir neçə marketdə ola
bilər. Market silinəndə onun YEGANƏ satıcısı olduğu məhsullar qiymətsiz
qalır: bazada var, amma heç bir yerdə görünmür və heç nəyə yaramır. Onları
da silirik, əks halda `products` sayğacı istifadəçiyə olmayan kataloq
vəd edərdi.

EHTİYAT NÜSXƏ HƏMİŞƏ GÖTÜRÜLÜR (`--apply` ilə). Fayl adı vaxt möhürlüdür,
yəni köhnə nüsxənin üstünə yazılmır.
"""

import argparse
import shutil
import sys
from datetime import datetime

from app.config import settings
from app.db import get_connection
from app.stores import market_for


def _counts(conn, store_id: int) -> dict:
    """Silinəcək sətirlərin sayı - `--apply`-dan ƏVVƏL göstərilir."""
    q = conn.execute
    orphans = q(
        "SELECT COUNT(*) FROM products p "
        "WHERE EXISTS (SELECT 1 FROM prices WHERE product_id = p.id AND store_id = ?) "
        "  AND NOT EXISTS (SELECT 1 FROM prices WHERE product_id = p.id AND store_id != ?)",
        (store_id, store_id),
    ).fetchone()[0]
    return {
        "prices": q("SELECT COUNT(*) FROM prices WHERE store_id = ?", (store_id,)).fetchone()[0],
        "catalogs": q("SELECT COUNT(*) FROM catalogs WHERE store_id = ?", (store_id,)).fetchone()[0],
        "snapshots": q(
            "SELECT COUNT(*) FROM price_snapshots WHERE store_id = ?", (store_id,)
        ).fetchone()[0],
        "orphan_products": orphans,
    }


def purge(slug: str, apply: bool) -> int:
    if market_for(slug) is not None:
        print(f"XƏTA: «{slug}» reyestrdəki marketdir - onu silmək olmaz.")
        return 1

    conn = get_connection()
    try:
        row = conn.execute("SELECT id, name FROM stores WHERE slug = ?", (slug,)).fetchone()
        if row is None:
            print(f"«{slug}» bazada yoxdur - silinəsi bir şey yoxdur.")
            return 0

        store_id, name = row["id"], row["name"]
        counts = _counts(conn, store_id)

        print(f"Market: {name} (slug={slug}, id={store_id})")
        for key, value in counts.items():
            print(f"  {key}: {value}")

        if not apply:
            print("\nBu, yalnız ÖN BAXIŞDIR. Silmək üçün: --apply")
            return 0

        # Ehtiyat nüsxə - silinmə geri dönməzdir.
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = settings.db_path.with_name(f"{settings.db_path.name}.bak-{stamp}")
        shutil.copy2(settings.db_path, backup)
        print(f"\nEhtiyat nüsxə: {backup}")

        # SIRA ƏHƏMİYYƏTLİDİR: əvvəl asılı sətirlər, sonra market.
        # Yetim məhsulların id-si qiymətlər silinməzdən ƏVVƏL yığılır -
        # sonra onları tapmaq mümkün olmazdı.
        orphan_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT p.id FROM products p "
                "WHERE EXISTS (SELECT 1 FROM prices WHERE product_id = p.id AND store_id = ?) "
                "  AND NOT EXISTS (SELECT 1 FROM prices WHERE product_id = p.id AND store_id != ?)",
                (store_id, store_id),
            )
        ]

        if orphan_ids:
            marks = ",".join("?" * len(orphan_ids))
            # Səbətdəki sətir də gedir: qiymətsiz məhsul səbətdə «tapılmadı»
            # kimi qalardı və istifadəçi onu silə bilməzdi.
            conn.execute(f"DELETE FROM basket_items WHERE product_id IN ({marks})", orphan_ids)

        conn.execute("DELETE FROM price_snapshots WHERE store_id = ?", (store_id,))
        conn.execute("DELETE FROM prices WHERE store_id = ?", (store_id,))
        conn.execute("DELETE FROM catalogs WHERE store_id = ?", (store_id,))
        if orphan_ids:
            marks = ",".join("?" * len(orphan_ids))
            conn.execute(f"DELETE FROM products WHERE id IN ({marks})", orphan_ids)
        conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))
        conn.commit()

        left = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        print(f"Silindi. Bazada qalan məhsul: {left}")
        return 0
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reyestrdən kənar marketi bazadan silir")
    parser.add_argument("slug", help="market slug-ı")
    parser.add_argument("--apply", action="store_true", help="həqiqətən sil")
    args = parser.parse_args()
    return purge(args.slug, args.apply)


if __name__ == "__main__":
    sys.exit(main())
