"""
Pipeline: kataloq mətni -> təmiz sətirlər -> LLM atributları -> verilənlər bazası.

Burada iki mənbə BİRLƏŞİR:
    qiymət      <- regex (ingestion/cleaner.py)   deterministik, uydurulmur
    atributlar  <- LLM   (ai/chains.py)           mətni başa düşmək tələb edir

Hər ikisi eyni sətirdən gəlir və sıra ilə birləşdirilir. Ona görə LLM-ə
sətirləri BİR-BİR göndəririk - qruplaşdırsaq, cavabların sırası pozula bilər
və qiymət səhv məhsula yapışar.
"""

from dataclasses import dataclass

from ai.chains import extract_attributes
from app.db import db_cursor, get_connection
from app.models import ExtractedProduct
from ingestion.cleaner import clean_text
from ingestion.normalize import canonical_key, unit_price


@dataclass
class PipelineResult:
    catalog_id: int
    store: str
    total_lines: int
    processed: int
    saved: int
    skipped: int
    llm: dict
    products: list[ExtractedProduct]

    def as_dict(self) -> dict:
        return {
            "catalog_id": self.catalog_id,
            "store": self.store,
            "total_lines": self.total_lines,
            "processed": self.processed,
            "saved": self.saved,
            "skipped": self.skipped,
            "llm": self.llm,
            "products": [p.model_dump() for p in self.products],
        }


def build_products(lines, attributes_list) -> tuple[list[ExtractedProduct], int]:
    """Təmiz sətir + LLM atributları -> yekun məhsul obyekti."""
    products: list[ExtractedProduct] = []
    skipped = 0

    for line, attrs in zip(lines, attributes_list):
        # LLM uğursuz oldu, ya da sətri məhsul saymadı
        if attrs is None or not attrs.name:
            skipped += 1
            continue
        # Qiymət regex ilə tapılmayıbsa məhsul yaza bilmərik
        if line.price is None:
            skipped += 1
            continue

        u_price, base = unit_price(line.price, attrs.size_value, attrs.size_unit)

        products.append(
            ExtractedProduct(
                name=attrs.name,
                brand=attrs.brand,
                size_value=attrs.size_value,
                size_unit=attrs.size_unit,
                category=attrs.category,
                price=line.price,
                old_price=line.old_price,
                unit_price=u_price,
                base_unit=base,
                canonical_key=canonical_key(
                    attrs.name, attrs.brand, attrs.size_value, attrs.size_unit
                ),
                raw_line=line.raw,
            )
        )

    return products, skipped


def save_products(products: list[ExtractedProduct], store_id: int, catalog_id: int) -> int:
    """
    Məhsulları və qiymətləri DB-yə yazır.

    Eyni kataloq təkrar emal olunarsa, əvvəlki qiymət sətirləri silinir -
    beləliklə təkrar işə salmaq təhlükəsizdir (idempotent).
    """
    with db_cursor() as cur:
        cur.execute("DELETE FROM prices WHERE catalog_id = ?", (catalog_id,))

        for product in products:
            # products cədvəlində canonical_key unikaldır -> upsert
            # group_key başlanğıcda canonical_key-ə bərabərdir. Matching işlədikdən
            # sonra birləşən məhsullar ortaq group_key alır - ona görə burada
            # mövcud group_key-ə TOXUNMURUQ (əks halda matching nəticəsi silinərdi).
            cur.execute(
                "INSERT INTO products (canonical_key, name, brand, size_value, size_unit, "
                "                      category, group_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(canonical_key) DO UPDATE SET "
                "  name = excluded.name, brand = excluded.brand, category = excluded.category",
                (
                    product.canonical_key,
                    product.name,
                    product.brand,
                    product.size_value,
                    product.size_unit,
                    product.category,
                    product.canonical_key,
                ),
            )
            cur.execute(
                "SELECT id FROM products WHERE canonical_key = ?", (product.canonical_key,)
            )
            product_id = cur.fetchone()[0]

            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price, old_price, "
                "                    unit_price, raw_line) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    product_id,
                    store_id,
                    catalog_id,
                    product.price,
                    product.old_price,
                    product.unit_price,
                    product.raw_line,
                ),
            )

    return len(products)


def extract_catalog(
    catalog_id: int,
    text: str,
    store_id: int,
    store_name: str,
    limit: int | None = None,
    use_cache: bool = True,
) -> PipelineResult:
    """
    Kataloqun mətnini AI ilə emal edir və nəticəni DB-yə yazır.

    limit: yalnız ilk N sətri emal et. GPU-suz maşında sınaq üçün vacibdir -
    bütün kataloqu gözləmədən nəticəni görürsən.
    """
    cleaned = clean_text(text)
    lines = cleaned.lines[:limit] if limit else cleaned.lines

    report = extract_attributes([line.text for line in lines], use_cache=use_cache)
    products, skipped = build_products(lines, report.results)

    saved = save_products(products, store_id, catalog_id)

    with db_cursor() as cur:
        cur.execute("UPDATE catalogs SET status = 'extracted' WHERE id = ?", (catalog_id,))

    return PipelineResult(
        catalog_id=catalog_id,
        store=store_name,
        total_lines=len(cleaned.lines),
        processed=len(lines),
        saved=saved,
        skipped=skipped,
        llm=report.as_dict(),
        products=products,
    )


def load_products(limit: int = 200) -> list[dict]:
    """Dashboard üçün: ən son qiymətlərlə birlikdə məhsul siyahısı."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT p.id, p.name, p.brand, p.size_value, p.size_unit, p.category, "
            "       pr.price, pr.old_price, pr.unit_price, pr.raw_line, pr.seen_at, "
            "       s.name AS store_name "
            "FROM prices pr "
            "JOIN products p ON p.id = pr.product_id "
            "JOIN stores s ON s.id = pr.store_id "
            "ORDER BY pr.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
