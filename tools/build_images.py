"""
Kataloq səhifələrindən məhsul şəkillərini kəsir və bazaya yazır.

    python -m tools.build_images              # bütün kataloqlar
    python -m tools.build_images --catalog 18 # yalnız biri
    python -m tools.build_images --force      # mövcud şəkilləri də yenidən kəs

NECƏ İŞLƏYİR (təfərrüat: `ingestion/images.py`):
    kataloq faylı -> səhifə şəkli -> kart analizi -> kartın xanası
    -> `prices.raw_line` ilə uyğunlaşdırma -> kəsib saxlama -> `image_path`

TESSERACT LAZIMDIR: kart analizi OCR-a əsaslanır. Tesseract quraşdırılmayıbsa,
script səbəbi yazıb dayanır - şəkilsiz məhsul UI-da placeholder alır, yəni
tətbiq onsuz da işləyir.
"""

import argparse
import sys

from app.db import get_connection
from app.config import settings
from ingestion.images import (
    MATCH_THRESHOLD,
    CropReport,
    catalog_pages,
    cell_box,
    _grid_steps,
    save_crop,
    similarity,
)


def build_for_catalog(catalog_id: int, force: bool) -> CropReport:
    from ingestion.layout import parse_page

    report = CropReport(catalog_id=catalog_id)
    conn = get_connection()
    try:
        catalog = conn.execute(
            "SELECT id, file_path FROM catalogs WHERE id = ?", (catalog_id,)
        ).fetchone()
        if catalog is None:
            print(f"kataloq {catalog_id} tapılmadı")
            return report

        # Bu kataloqdan gələn qiymətlər + onların orijinal OCR sətri.
        rows = conn.execute(
            "SELECT pr.product_id, pr.raw_line, pr.price, p.image_path "
            "FROM prices pr JOIN products p ON p.id = pr.product_id "
            "WHERE pr.catalog_id = ? AND pr.raw_line IS NOT NULL",
            (catalog_id,),
        ).fetchall()

        targets = [
            {
                "product_id": r["product_id"],
                "raw_line": r["raw_line"],
                "price": float(r["price"]),
            }
            for r in rows
            if force or not r["image_path"]
        ]
        if not targets:
            print(f"kataloq {catalog_id}: şəkli olmayan məhsul yoxdur")
            return report

        path = settings.base_dir / catalog["file_path"]
        if not path.exists():
            # Kataloq faylı silinibsə şəkil kəsmək mümkün deyil - bu, səhv
            # deyil, sadəcə mənbənin yoxluğudur.
            print(f"kataloq {catalog_id}: fayl yoxdur ({path})")
            return report

        saved: list[tuple[int, str]] = []
        for page in catalog_pages(path):
            report.pages += 1
            layout = parse_page(page)
            cards = [c for c in layout.cards if c.box != (0, 0, 0, 0)]
            report.cards += len(cards)
            if not cards:
                continue

            col_step, row_step = _grid_steps([c.box for c in cards], page)

            for target in list(targets):
                # QİYMƏT BİRİNCİ AÇARDIR, mətn ikinci.
                #
                # Yalnız mətn oxşarlığı ilə axtaranda şəkillər səhv məhsula
                # düşürdü: kataloqda «ETTA Dəftər» və «ETTA Plastilin» kimi
                # sətirlər bir-birinə çox oxşayır və OCR fərqi daha da azaldır.
                # Qiymət isə rəqəmdir - eyni səhifədə eyni qiymətli kart azdır,
                # ona görə əvvəlcə qiymətə görə namizədləri daraldırıq.
                priced = [
                    c
                    for c in cards
                    if c.price is not None and abs(c.price - target["price"]) < 0.005
                ]
                pool = priced or cards

                scored = sorted(
                    ((similarity(target["raw_line"], c.as_line()), c) for c in pool),
                    key=lambda pair: pair[0],
                    reverse=True,
                )
                score, best = scored[0] if scored else (0.0, None)

                if best is None:
                    continue

                # HƏDD 0.30 İDİ VƏ SƏHV ŞƏKİL VERİRDİ. Ölçüldü: «Düşbərə Tac
                # 300 q 3,99» sətri «ASH Su qabı 3,99» kartı ilə eyni qiymətə
                # düşür və qısa sətirlərdə oxşarlıq 0.3-ü keçir - nəticədə
                # düşbərənin yerinə su qabının şəkli görünürdü. Qiymət
                # namizədi daraldır, amma TƏK BAŞINA sübut deyil.
                if score < MATCH_THRESHOLD:
                    report.skipped_weak += 1
                    continue

                # İki namizəd bir-birinə çox yaxındırsa, hansının doğru
                # olduğunu bilmirik - səhv şəkildənsə placeholder yaxşıdır.
                if len(scored) > 1 and score - scored[1][0] < 0.05:
                    report.skipped_weak += 1
                    continue

                report.matched += 1
                box = cell_box(best.box, col_step, row_step, page)
                filename = save_crop(page, box, f"p{target['product_id']}")
                if filename:
                    saved.append((target["product_id"], filename))
                    report.saved += 1
                # Uyğunlaşan məhsul növbəti səhifədə təkrar axtarılmır.
                targets.remove(target)

        for product_id, filename in saved:
            conn.execute(
                "UPDATE products SET image_path = ? WHERE id = ?", (filename, product_id)
            )
        conn.commit()
        return report
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Kataloqdan məhsul şəkilləri kəsir")
    parser.add_argument("--catalog", type=int, help="yalnız bu kataloq")
    parser.add_argument("--force", action="store_true", help="mövcud şəkilləri də yenilə")
    args = parser.parse_args()

    conn = get_connection()
    try:
        if args.catalog:
            ids = [args.catalog]
        else:
            ids = [r["id"] for r in conn.execute("SELECT id FROM catalogs ORDER BY id")]
    finally:
        conn.close()

    total = 0
    for catalog_id in ids:
        report = build_for_catalog(catalog_id, args.force)
        print(report.as_line())
        total += report.saved

    print(f"\nCəmi {total} şəkil saxlanıldı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
