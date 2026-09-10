"""
Mağaza (sayt) qatı endpoint-ləri: onlayn mağazadan gündəlik qiymət çəkilişi.

`scrape.py` KATALOQ çəkir (həftəlik jurnal, `prices` cədvəli), bu isə
MAĞAZA çəkir (rəf qiyməti, `price_snapshots(source='site')`). İkisi ayrı
endpoint-dir, çünki ayrı qatdır - bax `ingestion/shop.py` başlığı.

Niyə sinxron? `scrape.py`-dakı ilə eyni səbəb: layihədə növbə sistemi yoxdur.
Onun əvəzinə `max_categories` limiti var - bir kateqoriya ~30 saniyədir, yəni
çağıran nə qədər gözləyəcəyini əvvəlcədən bilir.
"""

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from app.db import get_connection
from app.security import require_admin
from app.stores import market_for
from ingestion.ingest import get_or_create_store
from ingestion.pipeline import save_snapshots
from ingestion.profiles import PROFILES
from ingestion.shop import ShopError, scrape_shop

router = APIRouter(prefix="/api/shop", tags=["shop"], dependencies=[Depends(require_admin)])


def resolve_store_id(slug: str) -> int:
    """
    Reyestr slug-u -> `stores.id`. YENİ SƏTİR YARATMIR, əgər market artıq varsa.

    NİYƏ `get_or_create_store(market.name)` DEYİL? O, ADI slug-a çevirir:
    «Bravo Market» -> `bravo-market`. Bazadakı mövcud sətrin slug-u isə
    `bravo`-dur - yəni funksiya İKİNCİ market yaradardı və marketin datası
    iki sətrə bölünərdi. Bu, layihədə bir dəfə baş verib (`STORE_MERGES`-dəki
    `araz-market` -> `araz`) və eyni tələyə ikinci dəfə düşdük.

    İndi əvvəlcə reyestrin BÜTÜN aliasları yoxlanılır; yalnız heç biri
    tapılmasa yeni sətir yaradılır.
    """
    market = market_for(slug)
    if market is None:
        return get_or_create_store(slug)

    conn = get_connection()
    try:
        marks = ",".join("?" * len(market.all_slugs))
        row = conn.execute(
            f"SELECT id FROM stores WHERE slug IN ({marks}) ORDER BY id LIMIT 1",
            market.all_slugs,
        ).fetchone()
        if row:
            return row["id"]
    finally:
        conn.close()

    # Market bazada yoxdur - KANONİK slug ilə yaradılır.
    return get_or_create_store(market.slug)


def check_api_key(x_api_key: str | None) -> None:
    """Açar yalnız production-da tələb olunur (`scrape.py` ilə eyni qayda)."""
    if not settings.is_production:
        return
    if x_api_key != settings.ingest_api_key:
        raise HTTPException(401, "X-API-Key düzgün deyil")


@router.get("/sources")
def list_shop_sources():
    """
    Hansı marketlərin MAĞAZA mənbəyi var?

    `scrape/sources` kataloq mənbələrini sayır; bu isə mağaza mənbələrini.
    İki siyahı üst-üstə DÜŞMÜR və düşməməlidir: Arazda kataloq var, mağaza
    yoxdur; Bravoda əksinə.
    """
    out = []
    for slug, profile in PROFILES.items():
        market = market_for(slug)
        out.append(
            {
                "slug": slug,
                "store": market.name if market else slug,
                "shop_url": profile.shop_url,
                "shoppable": profile.shoppable,
                "note": profile.note,
            }
        )
    return {"sources": out}


@router.post("/{slug}")
def run_shop_scrape(
    slug: str,
    max_categories: int = 0,
    max_products: int = 0,
    dry_run: bool = False,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Marketin onlayn mağazasını çəkir və `price_snapshots`-a yazır.

    max_categories=0 / max_products=0 -> LİMİTSİZ (`scrape.py`-dakı
    `max_pages=0` ilə eyni qayda: sıfır «limit yoxdur» deməkdir).

    dry_run=True -> çəkilir, amma YAZILMIR. Səhifə strukturu dəyişəndə
    əvvəlcə nəyin çıxdığını görmək üçün.
    """
    check_api_key(x_api_key)

    try:
        report = scrape_shop(
            slug,
            max_categories=max_categories or None,
            max_products=max_products or None,
        )
    except ShopError as e:
        raise HTTPException(400, str(e))

    if report.products and not dry_run:
        store_id = resolve_store_id(slug)
        report.saved = save_snapshots(report.products, store_id, source="site")

    payload = report.as_dict()
    payload["dry_run"] = dry_run
    return payload


@router.get("/{slug}/stats")
def shop_stats(slug: str):
    """
    Marketin mağaza qatının vəziyyəti: neçə məhsul, neçə snapshot, son tarix.

    Çəkilişdən sonra nəticəni yoxlamaq üçün - bütün bazanı açmadan.
    """
    market = market_for(slug)
    if market is None:
        raise HTTPException(404, f"Market tanınmır: {slug}")

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT ps.product_id) AS products,
                   COUNT(ps.id)                  AS snapshots,
                   MAX(ps.observed_at)           AS last_seen,
                   SUM(ps.is_promo)              AS promos
            FROM price_snapshots ps
            JOIN stores s ON s.id = ps.store_id
            WHERE ps.source = 'site' AND s.slug IN (%s)
            """
            % ",".join("?" * len(market.all_slugs)),
            market.all_slugs,
        ).fetchone()
    finally:
        conn.close()

    return {
        "slug": market.slug,
        "store": market.name,
        "products": row["products"] or 0,
        "snapshots": row["snapshots"] or 0,
        "promos": row["promos"] or 0,
        "last_seen": row["last_seen"],
    }
