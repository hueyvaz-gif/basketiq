"""
Qiyməti olmayan («yetim») məhsulları bazadan silir.

    python -m tools.purge_orphans           # nə silinəcəyini göstərir
    python -m tools.purge_orphans --apply   # həqiqətən silir

YETİM MƏHSUL NECƏ YARANIR?
Kataloq yenidən emal olunanda `save_products()` həmin kataloqun BÜTÜN qiymət
sətirlərini silir və yenidən yazır (idempotentlik üçün). `products` cədvəlinə
isə toxunmur - `canonical_key` üzrə upsert edir. Nəticədə əvvəlki emalda
yaranmış, amma bu dəfə çıxmayan məhsul bazada QALIR: qiyməti yoxdur.

Ölçüldü (2026-09-09, 137-ci kataloqun yenidən emalından sonra): 214 məhsuldan
140-ı belə qalmışdı - yəni bazadakı hər üç sətirdən ikisi ölü idi.

NİYƏ SİLİRİK?
İstifadəçi panelində belə məhsul onsuz da görünmür (`app/catalog.py` yalnız
qiyməti olanları göstərir), amma:
  - admin panelindəki «məhsul sayı» sayğacı istifadəçiyə olmayan kataloq
    vəd edir;
  - matching statistikası ölü sətirlər üzərində hesablanır;
  - səbətdə qalan belə məhsul «qiyməti tapılmadı» kimi ilişib qalır.

ŞƏKİL FAYLI DA GEDİR: `app/static/images/products/p<id>.jpg` yalnız həmin
məhsula aiddir; məhsul silinəndə fayl sahibsiz qalar və növbəti `build_images`
qaçışı onu heç vaxt üzərinə yazmaz (id artıq mövcud deyil).

EHTİYAT NÜSXƏ HƏMİŞƏ GÖTÜRÜLÜR (`--apply` ilə), fayl adı vaxt möhürlüdür.
"""

import argparse
import shutil
import sys
from datetime import datetime

from app.config import settings
from app.db import get_connection
from ingestion.images import PRODUCT_IMAGE_DIR

ORPHAN_SQL = (
    "SELECT p.id, p.name, p.brand, p.image_path FROM products p "
    "WHERE NOT EXISTS (SELECT 1 FROM prices WHERE product_id = p.id) "
    "ORDER BY p.id"
)


def purge(apply: bool, preview: int = 15) -> int:
    conn = get_connection()
    try:
        orphans = conn.execute(ORPHAN_SQL).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

        if not orphans:
            print(f"Yetim məhsul yoxdur (bazada {total} məhsul).")
            return 0

        ids = [r["id"] for r in orphans]
        in_basket = conn.execute(
            "SELECT COUNT(*) FROM basket_items WHERE product_id IN "
            f"({','.join('?' * len(ids))})",
            ids,
        ).fetchone()[0]
        snapshots = conn.execute(
            "SELECT COUNT(*) FROM price_snapshots WHERE product_id IN "
            f"({','.join('?' * len(ids))})",
            ids,
        ).fetchone()[0]
        with_image = [r for r in orphans if r["image_path"]]

        print(f"Bazada {total} məhsul, bunlardan {len(orphans)}-i qiymətsizdir.")
        print(f"  səbət sətri: {in_basket}")
        print(f"  qiymət anlıq görüntüsü (price_snapshots): {snapshots}")
        print(f"  silinəcək şəkil faylı: {len(with_image)}")
        print("\nNümunə:")
        for row in orphans[:preview]:
            brand = f" [{row['brand']}]" if row["brand"] else ""
            print(f"  #{row['id']} {row['name']}{brand}")
        if len(orphans) > preview:
            print(f"  ... və daha {len(orphans) - preview} məhsul")

        if not apply:
            print("\nBu, yalnız ÖN BAXIŞDIR. Silmək üçün: --apply")
            return 0

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = settings.db_path.with_name(f"{settings.db_path.name}.bak-{stamp}")
        shutil.copy2(settings.db_path, backup)
        print(f"\nEhtiyat nüsxə: {backup}")

        marks = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM basket_items WHERE product_id IN ({marks})", ids)
        conn.execute(f"DELETE FROM price_snapshots WHERE product_id IN ({marks})", ids)
        conn.execute(f"DELETE FROM products WHERE id IN ({marks})", ids)
        conn.commit()

        # Şəkil faylı bazadan SONRA silinir: silinmə yarıda qalsa, bazada
        # şəkilsiz sətir qalmaqdansa, diskdə sahibsiz fayl qalsın - birincisi
        # ekranda sınıq şəkil deməkdir, ikincisi sadəcə boş yer.
        removed = 0
        for row in with_image:
            path = PRODUCT_IMAGE_DIR / row["image_path"]
            if path.exists():
                path.unlink()
                removed += 1

        left = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        print(f"Silindi: {len(ids)} məhsul, {removed} şəkil. Bazada qalan: {left}")
        return 0
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Qiymətsiz məhsulları bazadan silir")
    parser.add_argument("--apply", action="store_true", help="həqiqətən sil")
    args = parser.parse_args()
    return purge(apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
