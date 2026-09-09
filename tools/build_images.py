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
    CropReport,
    assign_cards,
    better_reason,
    catalog_pages,
    cell_box,
    _grid_steps,
    save_crop,
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
        unmatched: dict[int, str] = {}
        for page in catalog_pages(path):
            report.pages += 1
            layout = parse_page(page)
            cards = [c for c in layout.cards if c.box != (0, 0, 0, 0)]
            report.cards += len(cards)
            if not cards:
                continue

            col_step, row_step = _grid_steps([c.box for c in cards], page)

            # Uyğunlaşdırma BÜTÖV halda aparılır: hansı məhsulun hansı kartı
            # alacağı bütün iddialar hesablanandan sonra qərara alınır
            # (`ingestion.images.assign_cards`). Məhsul-məhsul gəzsək, kartı
            # «birinci gələn» alardı və bir kart iki məhsula düşərdi.
            winners, why = assign_cards(targets, cards)
            # Səbəb HƏLƏ SAYILMIR: məhsul bu səhifədə tapılmaya bilər, amma
            # növbətidə tapılar. Sayğac yalnız sonda, şəkilsiz qalanlar üzrə
            # doldurulur - əks halda hər səhifə eyni məhsulu yenidən sayardı.
            for product_id, reason in why.items():
                unmatched[product_id] = better_reason(unmatched.get(product_id), reason)

            for win in winners:
                report.matched += 1
                box = cell_box(cards[win.card_index].box, col_step, row_step, page)
                filename = save_crop(page, box, f"p{win.product_id}")
                if filename:
                    saved.append((win.product_id, filename))
                    report.saved += 1
                else:
                    report.skipped["boş kadr"] = report.skipped.get("boş kadr", 0) + 1
                # Uyğunlaşan məhsul növbəti səhifədə təkrar axtarılmır.
                targets = [t for t in targets if t["product_id"] != win.product_id]

        # Yalnız şəkilsiz qalanlar sayılır: uyğunlaşan məhsul əvvəlki
        # səhifədə hansısa səbəb almışdısa, o səbəb artıq keçərli deyil.
        matched_ids = {product_id for product_id, _ in saved}
        for product_id, reason in unmatched.items():
            if product_id not in matched_ids:
                report.skipped[reason] = report.skipped.get(reason, 0) + 1

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
