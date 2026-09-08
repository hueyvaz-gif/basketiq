"""
Məhsul kataloqu — trolley.co.uk üslubundakı ekranların data qatı.

BURADA ÜÇ SUALA CAVAB VERİLİR:
    1. «Bu gün ən böyük endirim hansı məhsuldadır?»  -> todays_deals()
    2. «Bu məhsulu harada almaq lazımdır?»            -> product_detail()
    3. «Hansı ölçü daha sərfəlidir?»                  -> variants (aşağıda)

ƏSAS QAYDA — BOŞ SÜTUN YOXDUR.
Trolley-də dörd market dörd sütundur, çünki onların hər market üçün tam
kataloqu var. Bizdə yoxdur: `logs/sources.md`-dəki ölçmələrə görə Bazar Store
və Rahat Market üçün heç bir mənbə çəkilə bilmir. Ona görə cədvəl SÜTUN
üzərində yox, SƏTİR üzərində qurulur: məhsulun qiyməti hansı marketlərdə
varsa, o qədər sətir olur. Market datası yoxdursa, sətir ÜMUMİYYƏTLƏ
yaranmır — nə boş xana, nə «0.00», nə də xəta.

Hazır olmayan marketlərin adı UI-dan tamamilə silinmir: `app/stores.py`
onları `available=False` ilə qaytarır və səhifə altda «Tezliklə» yazır.
Beləliklə istifadəçi «niyə cəmi iki market?» sualının cavabını görür.

İKİNCİ QAYDA — «ƏN UCUZ» İLƏ «ƏN SƏRFƏLİ» EYNİ ŞEY DEYİL.
    ən ucuz   = mütləq qiymət (cibdən çıxan pul)
    ən sərfəli = vahid qiyməti (1 kq / 1 L)
2 litrlik yağ 1 litrlikdən HƏMİŞƏ bahadır, amma adətən daha sərfəlidir.
İki nişan ayrı-ayrı hesablanır və ayrı-ayrı göstərilir; birini digərinin
yerinə işlətmək istifadəçini yanıldar.
"""

from sqlite3 import Connection

from app.analytics import IMPLAUSIBLE_DEPTH
from app.db import get_connection
from app.stores import Market, market_for, market_status, store_map
from ingestion.normalize import display_label, display_size, unit_price

# Endirim bu dərinlikdən keçirsə, siyahıya BURAXILMIR.
#
# Səbəb `app/analytics.py`-də sənədləşdirilib: ərzaqda 70%-dən dərin endirim
# praktiki olaraq olmur, yəni belə sətir ya OCR səhvidir, ya da uydurma köhnə
# qiymətdir. «Bugünün ən sərfəli endirimləri» bölməsi məhz ƏN BÖYÜK faizlə
# başladığı üçün süzgəcsiz qalsa, siyahının başında həmişə zibil dayanardı.
MAX_DEPTH = IMPLAUSIBLE_DEPTH

# Endirim sayılmaq üçün minimum faiz. 1-2% dəyişmə kataloqda «endirim» kimi
# yazılsa da, istifadəçi üçün qərar dəyişmir.
MIN_DISCOUNT_PCT = 3.0


# ------------------------------------------------------------------ təkliflər


def _offer_row(row, market: Market) -> dict:
    """Bir `prices` sətrindən UI-nin oxuduğu «təklif» obyekti."""
    price = float(row["price"])
    old = row["old_price"]
    old = float(old) if old is not None else None

    # Endirim faizi BURADA hesablanır, LLM-də yox (bax `app/models.py`).
    pct = None
    if old and old > price:
        pct = round((old - price) * 100 / old, 1)

    unit = row["unit_price"]
    base = None
    if unit is None:
        # Bazada boşdursa özümüz hesablayırıq: köhnə sətirlərdə bu sütun
        # doldurulmayıb və «ən sərfəli» nişanı onsuz işləmir.
        unit, base = unit_price(price, row["size_value"], row["size_unit"])
    else:
        unit = float(unit)
        _, base = unit_price(price, row["size_value"], row["size_unit"])

    return {
        "product_id": row["product_id"],
        "store_slug": market.slug,
        "store": market.name,
        "store_short": market.short,
        "price": round(price, 2),
        "old_price": round(old, 2) if old else None,
        "discount_pct": pct,
        "unit_price": round(unit, 2) if unit else None,
        "base_unit": base,
        "size": display_size(row["size_value"], row["size_unit"]),
        "seen_at": row["seen_at"],
        # Aşağıdakı `_rank_offers()` doldurur
        "is_cheapest": False,
        "is_best_value": False,
    }


def _rank_offers(offers: list[dict]) -> list[dict]:
    """
    Təklifləri ucuzdan bahaya düzür və iki nişanı qoyur.

    NİŞAN TƏK OLANDA VERİLMİR: bir market varsa, «ən ucuz» heç nə demir —
    müqayisə yoxdur. Trolley-də də tək təklifin yanında nişan olmur.
    """
    offers.sort(key=lambda o: (o["price"], o["store"]))
    if len(offers) < 2:
        return offers

    cheapest = min(o["price"] for o in offers)
    for offer in offers:
        offer["is_cheapest"] = offer["price"] == cheapest

    # «Ən sərfəli» nişanı YALNIZ «ən ucuz»dan FƏRQLƏNƏNDƏ qoyulur.
    #
    # Səbəb: bir məhsulun bütün təklifləri eyni ölçüdədir (məhsul elə ölçü ilə
    # birlikdə müəyyən olunur), yəni vahid qiyməti = qiymət / sabit ölçü.
    # Belə halda iki nişan HƏMİŞƏ eyni sətrə düşür və ikincisi heç nə demir.
    # Fərq yalnız ölçüsü fərqli yazılmış sətirlərdə yaranır — məhz onda
    # nişan istifadəçiyə yeni məlumat verir.
    with_unit = [o for o in offers if o["unit_price"] is not None]
    if len(with_unit) >= 2:
        best_unit = min(o["unit_price"] for o in with_unit)
        winner = next(o for o in with_unit if o["unit_price"] == best_unit)
        if not winner["is_cheapest"]:
            for offer in with_unit:
                offer["is_best_value"] = offer["unit_price"] == best_unit
    return offers


def _offers_by_group(
    conn: Connection, group_keys: list[str], markets: dict[int, Market]
) -> dict[str, list[dict]]:
    """
    Bir neçə məhsul qrupunun bütün təkliflərini BİR sorğuda gətirir.

    Niyə bir sorğu? «Bugünün endirimləri» 12 kartdır və hər kartda market
    müqayisəsi var. Hər kart üçün ayrıca sorğu 12 dəfə baza gedişi deməkdir —
    SQLite-da ucuz olsa da, bu, N+1 vərdişini layihəyə gətirər.

    EYNİ MARKETDƏN BİR NEÇƏ MÜŞAHİDƏ: `prices` cədvəli tarixçə saxlayır, yəni
    eyni məhsul eyni marketdə bir neçə kataloqda ola bilər. Cədvəldə ƏN SON
    müşahidə göstərilir — köhnə qiyməti cari kimi vermək yanlış olardı.
    """
    if not group_keys or not markets:
        return {}

    store_ids = list(markets)
    key_marks = ",".join("?" * len(group_keys))
    store_marks = ",".join("?" * len(store_ids))

    rows = conn.execute(
        f"""
        SELECT p.group_key   AS group_key,
               p.id          AS product_id,
               p.size_value  AS size_value,
               p.size_unit   AS size_unit,
               pr.store_id   AS store_id,
               pr.price      AS price,
               pr.old_price  AS old_price,
               pr.unit_price AS unit_price,
               pr.seen_at    AS seen_at
        FROM prices pr
        JOIN products p ON p.id = pr.product_id
        WHERE p.group_key IN ({key_marks})
          AND pr.store_id IN ({store_marks})
        ORDER BY pr.seen_at, pr.id
        """,
        (*group_keys, *store_ids),
    ).fetchall()

    # (qrup, market) -> son sətir. Sorğu tarix üzrə artan sıradadır, ona görə
    # sonuncu yazı sadəcə əvvəlkini əvəz edir.
    latest: dict[tuple[str, str], dict] = {}
    for row in rows:
        market = markets[row["store_id"]]
        latest[(row["group_key"], market.slug)] = _offer_row(row, market)

    out: dict[str, list[dict]] = {}
    for (group_key, _), offer in latest.items():
        out.setdefault(group_key, []).append(offer)
    for offers in out.values():
        _rank_offers(offers)
    return out


def _compare_note(offers: list[dict]) -> dict | None:
    """
    Marketlər arası müqayisənin bir cümləlik xülasəsi.

    Tək market varsa None qayıdır və UI heç nə yazmır — «1 marketdə var»
    cümləsi yer tutur, məlumat vermir.
    """
    if len(offers) < 2:
        return None
    prices = [o["price"] for o in offers]
    cheapest = min(prices)
    dearest = max(prices)
    winner = next(o for o in offers if o["price"] == cheapest)
    return {
        "store": winner["store"],
        "store_short": winner["store_short"],
        "cheapest": round(cheapest, 2),
        "dearest": round(dearest, 2),
        "spread": round(dearest - cheapest, 2),
        "stores": len(offers),
    }


# --------------------------------------------------------------- endirimlər


def todays_deals(limit: int = 12) -> dict:
    """
    «Bugünün ən sərfəli endirimləri» — hər məhsul üçün ƏN BÖYÜK faiz endirim.

    HƏR MƏHSUL ÜÇÜN BİR SƏTİR: eyni məhsul iki marketdə endirimdədirsə,
    kartda böyük faiz göstərilir, kiçiyi isə kartın içindəki müqayisə
    cədvəlində qalır. Əks halda siyahının yarısı eyni məhsulun təkrarı olardı.
    """
    conn = get_connection()
    try:
        markets = store_map(conn)
        if not markets:
            return {"items": [], "markets": [], "note": "market datası yoxdur"}

        store_marks = ",".join("?" * len(markets))
        rows = conn.execute(
            f"""
            SELECT p.id           AS product_id,
                   p.group_key    AS group_key,
                   p.name         AS name,
                   p.brand        AS brand,
                   p.size_value   AS size_value,
                   p.size_unit    AS size_unit,
                   p.category     AS category,
                   pr.store_id    AS store_id,
                   pr.price       AS price,
                   pr.old_price   AS old_price,
                   pr.seen_at     AS seen_at
            FROM prices pr
            JOIN products p ON p.id = pr.product_id
            WHERE pr.store_id IN ({store_marks})
              AND pr.old_price IS NOT NULL
              AND pr.old_price > pr.price
            ORDER BY pr.seen_at, pr.id
            """,
            tuple(markets),
        ).fetchall()

        best: dict[str, dict] = {}
        for row in rows:
            old = float(row["old_price"])
            price = float(row["price"])
            depth = (old - price) / old
            # Ağlabatmayan dərinlik (>70%) və cüzi endirim (<3%) atılır.
            if depth > MAX_DEPTH:
                continue
            pct = round(depth * 100, 1)
            if pct < MIN_DISCOUNT_PCT:
                continue

            market = markets[row["store_id"]]
            current = best.get(row["group_key"])
            if current and current["discount_pct"] >= pct:
                continue

            best[row["group_key"]] = {
                "product_id": row["product_id"],
                "group_key": row["group_key"],
                "label": display_label(row["name"], row["brand"]),
                "brand": row["brand"],
                "size": display_size(row["size_value"], row["size_unit"]),
                "category": row["category"],
                "store": market.name,
                "store_short": market.short,
                "store_slug": market.slug,
                "price": round(price, 2),
                "old_price": round(old, 2),
                "discount_pct": pct,
                "saving": round(old - price, 2),
            }

        ranked = sorted(
            best.values(), key=lambda d: (-d["discount_pct"], d["label"])
        )[:limit]

        offers = _offers_by_group(conn, [d["group_key"] for d in ranked], markets)
        for deal in ranked:
            deal["offers"] = offers.get(deal["group_key"], [])
            deal["compare"] = _compare_note(deal["offers"])

        return {"items": ranked, "total_found": len(best)}
    finally:
        conn.close()


# -------------------------------------------------------------- market səhifəsi


def store_page(slug: str, limit: int = 40) -> dict | None:
    """
    Bir marketin öz səhifəsi: endirimləri + məhsulları.

    Ana səhifədəki loqo şəbəkəsindən buraya gəlinir. Reyestrdə olmayan slug
    üçün None qayıdır (404), çünki uydurma market səhifəsi açmaq olmaz.

    DATASI OLMAYAN MARKET SƏHV DEYİL. Bazar Store və Rahat Market üçün mənbə
    hələ çəkilə bilmir, amma onların da səhifəsi AÇILIR — sadəcə boş siyahı
    və `available: False` ilə. Səhifə istifadəçiyə vəziyyəti izah edir; kartı
    kliklənməz etmək isə səbəbi gizlədərdi.
    """
    market = market_for(slug)
    if market is None:
        return None

    status = next((m for m in market_status() if m["slug"] == market.slug), None)

    conn = get_connection()
    try:
        markets = store_map(conn)
        own_ids = [sid for sid, m in markets.items() if m.slug == market.slug]
        if not own_ids:
            return {
                "market": status,
                "deals": [],
                "products": [],
            }

        own_marks = ",".join("?" * len(own_ids))
        rows = conn.execute(
            f"""
            SELECT p.id          AS product_id,
                   p.group_key   AS group_key,
                   p.name        AS name,
                   p.brand       AS brand,
                   p.size_value  AS size_value,
                   p.size_unit   AS size_unit,
                   p.category    AS category,
                   pr.price      AS price,
                   pr.old_price  AS old_price,
                   pr.seen_at    AS seen_at
            FROM prices pr
            JOIN products p ON p.id = pr.product_id
            WHERE pr.store_id IN ({own_marks})
            ORDER BY pr.seen_at, pr.id
            """,
            tuple(own_ids),
        ).fetchall()

        # Qrup üzrə ƏN SON müşahidə: `prices` tarixçə saxlayır, market
        # səhifəsində isə cari qiymət göstərilməlidir.
        latest: dict[str, dict] = {}
        for row in rows:
            price = float(row["price"])
            old = float(row["old_price"]) if row["old_price"] is not None else None
            pct = None
            if old and old > price:
                depth = (old - price) / old
                if depth <= MAX_DEPTH and depth * 100 >= MIN_DISCOUNT_PCT:
                    pct = round(depth * 100, 1)

            latest[row["group_key"]] = {
                "product_id": row["product_id"],
                "group_key": row["group_key"],
                "label": display_label(row["name"], row["brand"]),
                "brand": row["brand"],
                "size": display_size(row["size_value"], row["size_unit"]),
                "category": row["category"],
                "price": round(price, 2),
                "old_price": round(old, 2) if pct else None,
                "discount_pct": pct,
            }

        items = list(latest.values())
        deals = sorted(
            (i for i in items if i["discount_pct"]),
            key=lambda i: -i["discount_pct"],
        )[:limit]
        products = sorted(items, key=lambda i: i["label"])[:limit]

        # Endirim kartlarında market müqayisəsi də göstərilir: bu marketdəki
        # «50% endirim» qonşuda endirimsiz daha ucuz ola bilər.
        offers = _offers_by_group(conn, [d["group_key"] for d in deals], markets)
        for deal in deals:
            deal["offers"] = offers.get(deal["group_key"], [])
            deal["compare"] = _compare_note(deal["offers"])

        return {
            "market": status,
            "deals": deals,
            "products": products,
            "total_products": len(items),
            "total_deals": sum(1 for i in items if i["discount_pct"]),
        }
    finally:
        conn.close()


# ------------------------------------------------------------- məhsul səhifəsi


def _card_rows(
    conn: Connection,
    where: str,
    params: tuple,
    markets: dict[int, Market],
    limit: int,
) -> list[dict]:
    """
    «Oxşar məhsullar» / «Eyni brenddən» kartları.

    YALNIZ QİYMƏTİ OLAN MƏHSUL: qiyməti olmayan kart kliklənəndə boş səhifə
    açılardı. `products` cədvəlində 540 sətir var, amma onların çoxu
    reyestrdən kənar marketdən gəlib — belə məhsul bizim üçün mövcud deyil.
    """
    store_marks = ",".join("?" * len(markets))
    rows = conn.execute(
        f"""
        SELECT p.id          AS product_id,
               p.group_key   AS group_key,
               p.name        AS name,
               p.brand       AS brand,
               p.size_value  AS size_value,
               p.size_unit   AS size_unit,
               p.category    AS category,
               MIN(pr.price) AS price,
               COUNT(DISTINCT pr.store_id) AS store_count
        FROM products p
        JOIN prices pr ON pr.product_id = p.id
        WHERE pr.store_id IN ({store_marks}) AND {where}
        GROUP BY p.group_key
        ORDER BY store_count DESC, p.name
        LIMIT ?
        """,
        (*markets, *params, limit),
    ).fetchall()

    return [
        {
            "product_id": row["product_id"],
            "group_key": row["group_key"],
            "label": display_label(row["name"], row["brand"]),
            "brand": row["brand"],
            "size": display_size(row["size_value"], row["size_unit"]),
            "category": row["category"],
            "price": round(float(row["price"]), 2),
            "store_count": row["store_count"],
        }
        for row in rows
    ]


def _variants(
    conn: Connection, product: dict, markets: dict[int, Market]
) -> list[dict]:
    """
    Eyni məhsulun ölçü/paket variantları + «ən ucuz» və «ən sərfəli» nişanları.

    VARİANT NƏDİR? Eyni ad, eyni brend, FƏRQLİ ölçü: «Sola günəbaxan yağı
    1.8 L» ilə «Sola günəbaxan yağı 5 L». `group_key` ölçünü də daşıdığı üçün
    variantlar ayrı qruplardır — onları ad+brend üzrə birləşdiririk.

    Bir variant qalırsa boş siyahı qaytarılır: müqayisə olmayan yerdə nişan
    da olmamalıdır.
    """
    store_marks = ",".join("?" * len(markets))
    rows = conn.execute(
        f"""
        SELECT p.id          AS product_id,
               p.group_key   AS group_key,
               p.size_value  AS size_value,
               p.size_unit   AS size_unit,
               MIN(pr.price) AS price,
               COUNT(DISTINCT pr.store_id) AS store_count
        FROM products p
        JOIN prices pr ON pr.product_id = p.id
        WHERE pr.store_id IN ({store_marks})
          AND p.name = ?
          AND COALESCE(p.brand, '') = COALESCE(?, '')
        GROUP BY p.group_key
        ORDER BY price
        """,
        (*markets, product["name"], product["brand"]),
    ).fetchall()

    variants = []
    for row in rows:
        price = round(float(row["price"]), 2)
        unit, base = unit_price(price, row["size_value"], row["size_unit"])
        variants.append(
            {
                "product_id": row["product_id"],
                "group_key": row["group_key"],
                "size": display_size(row["size_value"], row["size_unit"]) or "—",
                "price": price,
                "unit_price": round(unit, 2) if unit else None,
                "base_unit": base,
                "store_count": row["store_count"],
                "is_current": row["group_key"] == product["group_key"],
                "is_cheapest": False,
                "is_best_value": False,
            }
        )

    if len(variants) < 2:
        return []

    cheapest = min(v["price"] for v in variants)
    for variant in variants:
        variant["is_cheapest"] = variant["price"] == cheapest

    with_unit = [v for v in variants if v["unit_price"] is not None]
    if len(with_unit) >= 2:
        best_unit = min(v["unit_price"] for v in with_unit)
        if any(v["unit_price"] != best_unit for v in with_unit):
            for variant in with_unit:
                variant["is_best_value"] = variant["unit_price"] == best_unit
    return variants


def product_detail(product_id: int) -> dict | None:
    """
    Məhsul səhifəsinin bütün datası. Məhsul tapılmasa None.

    Cavabın quruluşu birbaşa ekranın bölmələrinə uyğundur:
        product   -> başlıq
        offers    -> «Harada al» cədvəli
        variants  -> «Ölçü variantları» (ən ucuz / ən sərfəli nişanları)
        similar   -> «Oxşar məhsullar» (eyni kateqoriya)
        same_brand-> «Eyni brenddən»
        markets   -> dörd marketin statusu («Tezliklə» yazısı üçün)
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, group_key, name, brand, size_value, size_unit, category, "
            "       barcode, product_url "
            "FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row is None:
            return None

        product = {
            "id": row["id"],
            "group_key": row["group_key"],
            "name": row["name"],
            "brand": row["brand"],
            "label": display_label(row["name"], row["brand"]),
            "size": display_size(row["size_value"], row["size_unit"]),
            "category": row["category"],
            "barcode": row["barcode"],
            "product_url": row["product_url"],
        }

        markets = store_map(conn)
        if not markets:
            return {
                "product": product,
                "offers": [],
                "compare": None,
                "variants": [],
                "similar": [],
                "same_brand": [],
            }

        offers = _offers_by_group(conn, [product["group_key"]], markets).get(
            product["group_key"], []
        )

        similar = _card_rows(
            conn,
            "p.category = ? AND p.group_key != ?",
            (product["category"], product["group_key"]),
            markets,
            8,
        )

        same_brand: list[dict] = []
        if product["brand"]:
            same_brand = _card_rows(
                conn,
                "p.brand = ? AND p.group_key != ?",
                (product["brand"], product["group_key"]),
                markets,
                8,
            )

        return {
            "product": product,
            "offers": offers,
            "compare": _compare_note(offers),
            "variants": _variants(conn, product, markets),
            "similar": similar,
            "same_brand": same_brand,
        }
    finally:
        conn.close()
