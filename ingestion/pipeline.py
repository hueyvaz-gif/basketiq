"""
Pipeline: kataloq mətni -> təmiz sətirlər -> LLM atributları -> verilənlər bazası.

Burada iki mənbə BİRLƏŞİR:
    qiymət      <- regex (ingestion/cleaner.py)   deterministik, uydurulmur
    atributlar  <- LLM   (ai/chains.py)           mətni başa düşmək tələb edir

Hər ikisi eyni sətirdən gəlir və sıra ilə birləşdirilir. Ona görə LLM-ə
sətirləri BİR-BİR göndəririk - qruplaşdırsaq, cavabların sırası pozula bilər
və qiymət səhv məhsula yapışar.
"""

import json
import re
from dataclasses import dataclass

from ai.chains import extract_attributes
from app.db import db_cursor, get_connection
from app.models import ExtractedProduct
from ingestion.cleaner import clean_text
from ingestion.normalize import canonical_key, unit_price
from ingestion.quality import check_price


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


_NUMBER = re.compile(r"\d+[.,]?\d*")


def _number_count(text: str, value: float) -> int:
    """`value` rəqəmi sətirdə neçə dəfə yazılıb?"""
    found = 0
    for token in _NUMBER.findall(text or ""):
        try:
            if abs(float(token.replace(",", ".")) - value) < 1e-9:
                found += 1
        except ValueError:
            continue
    return found


def price_reused_as_size(line, size_value: float | None) -> bool:
    """
    Model QİYMƏTİ ölçü kimi köçürübmü?

    REAL SƏHVDƏN ÇIXIB. Sətirdə ölçü yazılmayanda model bəzən əlindəki
    yeganə rəqəmi - qiyməti - ölçü sahəsinə qoyur:

        «cay mi 1.25»                  -> ölçü 1.25 L, qiymət 1.25 ₼
        «Persil Уи toz 1.35»           -> ölçü 1.35 kg, qiymət 1.35 ₼
        «Bloom Ağardıcı vasitə 0.85»   -> ölçü 0.85 L, qiymət 0.85 ₼

    Nəticə görünəndən pisdir: `unit_price` həmişə TAM 1.0 çıxır, yəni «1 litri
    1 manat». Bu, kataloqdakı ən sərfəli təklif kimi görünür və «ən sərfəli»
    sıralamasının BAŞINA keçir - halbuki belə məhsul yoxdur.

    Şərt iki hissəlidir: rəqəm qiymətə bərabər OLMALI və sətirdə YALNIZ BİR
    DƏFƏ yazılmalıdır. İkinci şərt təsadüfi üst-üstə düşməni qoruyur: «1.5 L
    ... 1.50 ₼» sətrində həmin rəqəm iki dəfə görünür, deməli ölçü realdır.
    Ölçüldü: 137-ci kataloqda birinci şərtə 3 sətir düşür, hər üçündə rəqəm
    bir dəfədir; qiymətdən fərqli 62 ölçüyə isə toxunulmur.
    """
    if size_value is None:
        return False
    for candidate in (getattr(line, "price", None), getattr(line, "old_price", None)):
        if candidate is None or abs(size_value - candidate) > 1e-9:
            continue
        if _number_count(getattr(line, "raw", ""), size_value) <= 1:
            return True
    return False


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

        # Qiymət ölçü kimi köçürülübsə, ölçünü ATIRIQ - məhsulu yox.
        # Qiymət realdır, yalnız ölçü uydurmadır; sətri tamamilə atsaq,
        # kataloqdakı doğru qiyməti də itirərdik.
        size_value, size_unit = attrs.size_value, attrs.size_unit
        if price_reused_as_size(line, size_value):
            size_value, size_unit = None, None

        u_price, base = unit_price(line.price, size_value, size_unit)

        products.append(
            ExtractedProduct(
                name=attrs.name,
                brand=attrs.brand,
                size_value=size_value,
                size_unit=size_unit,
                category=attrs.category,
                price=line.price,
                old_price=line.old_price,
                unit_price=u_price,
                base_unit=base,
                canonical_key=canonical_key(attrs.name, attrs.brand, size_value, size_unit),
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

            # SAĞLAMLIQ YOXLAMASI (C12): şübhəli sətir bazaya DÜŞÜR, amma
            # nişanlanır. Atsaydıq, səhvi araşdırmaq mümkün olmazdı; nişansız
            # buraxsaydıq, zibil «bugünün endirimləri» siyahısına çıxardı.
            # Hədlər və izahları: `ingestion/quality.py`.
            flags = check_price(
                price=product.price,
                old_price=product.old_price,
                unit_price=product.unit_price,
            )
            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price, old_price, "
                "                    unit_price, raw_line, flags) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    product_id,
                    store_id,
                    catalog_id,
                    product.price,
                    product.old_price,
                    product.unit_price,
                    product.raw_line,
                    json.dumps(flags) if flags else None,
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
