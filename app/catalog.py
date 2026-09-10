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
from statistics import median

from app.analytics import IMPLAUSIBLE_DEPTH, SUSPICIOUS_DEPTH, verify_claim
from app.db import PRICE_ROWS_CTE, get_connection
from app.search_norm import match_score, tokens as norm_tokens
from app.similar import pick_similar
from app.stores import MARKETS, Market, market_for, market_status, store_map
from app.services.product_images import photo_map
from ingestion.images import image_url
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


def match_confidence(conn, group_keys: list[str]) -> dict[str, str]:
    """
    Hər qrup üçün: marketlərarası uyğunluq DƏQİQdir, yoxsa TƏXMİNİ?

    `canonical_key` addan, brenddən və ölçüdən qurulur (`ingestion/normalize`).
    Bir qrupdakı bütün məhsulların açarı EYNİDİRSƏ, marketlər eyni SKU-nu
    satır - müqayisə dəqiqdir. Açarlar fərqlidirsə, qrupu matcher birləşdirib
    (LLM + oxşarlıq) - yəni «Milla süd 1 l» ilə «Süd Milla 1L» eyni sayılıb.
    Bu, çox vaxt doğrudur, amma ZƏMANƏT DEYİL.

    NİYƏ İSTİFADƏÇİYƏ DEYİLİR? Qiymət müqayisəsinin bütün mənası məhsulların
    eyni olmasındadır. Təxmini uyğunluğu dəqiq kimi göstərmək müqayisəni
    yalançı dəqiqliklə bəzəməkdir.
    """
    if not group_keys:
        return {}
    marks = ",".join("?" * len(group_keys))
    rows = conn.execute(
        f"SELECT group_key, COUNT(DISTINCT canonical_key) AS n "
        f"FROM products WHERE group_key IN ({marks}) GROUP BY group_key",
        tuple(group_keys),
    ).fetchall()
    return {r["group_key"]: ("exact" if r["n"] <= 1 else "approximate") for r in rows}


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


def discount_pct(
    price: float | None,
    old_price: float | None,
    *,
    max_depth: float | None = MAX_DEPTH,
) -> float | None:
    """
    ENDİRİM FAİZİNİN YEGANƏ HESABLANDIĞI YER.

    NİYƏ AYRICA FUNKSİYA? Eyni hesablama üç yerdə təkrarlanırdı: market
    səhifəsi, «bugünün endirimləri» və məhsul kartı. Hədlər bir yerdə
    dəyişəndə digərləri köhnə qalırdı və nəticə İSTİFADƏÇİYƏ ZİDDİYYƏT kimi
    görünürdü: market səhifəsində «-16%» yazılır, ana səhifədə isə həmin
    məhsul ümumiyyətlə yoxdur.

    `max_depth=None` -> dərinlik həddi tətbiq OLUNMUR. «Bugünün endirimləri»
    məhz belə çağırır, çünki orada dərin endirim ATILMIR, əvvəlcə
    `verify_claim()` ilə yoxlanılır: tarixçə iddianı təsdiqləyirsə, 70%-dən
    dərin endirim də realdır (`todays_deals`-dakı izaha bax).

    Qaytarır: faiz (1 onluq) və ya None - endirim yoxdursa/həddən kənardırsa.
    """
    if price is None or old_price is None:
        return None
    price = float(price)
    old_price = float(old_price)
    if old_price <= price or old_price <= 0:
        return None

    depth = (old_price - price) / old_price
    if max_depth is not None and depth > max_depth:
        return None
    pct = round(depth * 100, 1)
    return pct if pct >= MIN_DISCOUNT_PCT else None


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
        # HƏR İKİ QİYMƏT QATI (`PRICE_ROWS_CTE`): kataloq iddiası + mağaza
        # rəf qiyməti.
        #
        # ƏVVƏL YALNIZ `prices` OXUNURDU və nəticə istifadəçiyə belə
        # görünürdü: siyahı demək olar tamamilə Arazdan ibarətdir. Səbəb
        # market deyil, SXEM idi - Bravonun 13 089 məhsulu `price_snapshots`
        # cədvəlindədir və o cədvəldə `old_price` sütunu ümumiyyətlə yox idi,
        # yəni 3 369 endirimli məhsul prinsipcə bura düşə bilmirdi.
        #
        # `flags` yalnız kataloq qatındadır - mağaza sətrində belə sütun
        # yoxdur, ona görə karantin şərti `layer = 'catalog'` üçün tətbiq
        # olunur. Mağaza qatının öz keyfiyyət yoxlaması `is_promo`-dur.
        rows = conn.execute(
            f"""
            {PRICE_ROWS_CTE}
            SELECT p.id           AS product_id,
                   p.group_key    AS group_key,
                   p.name         AS name,
                   p.brand        AS brand,
                   p.size_value   AS size_value,
                   p.size_unit    AS size_unit,
                   p.category     AS category,
                   p.image_path   AS image_path,
                   pr.product_id  AS price_id,
                   pr.store_id    AS store_id,
                   pr.price       AS price,
                   pr.old_price   AS old_price,
                   pr.at          AS seen_at,
                   pr.layer       AS layer
            FROM price_rows pr
            JOIN products p ON p.id = pr.product_id
            WHERE pr.store_id IN ({store_marks})
              AND pr.old_price IS NOT NULL
              AND pr.old_price > pr.price
              -- KARANTİN (C12): sağlamlıq yoxlamasından keçməyən sətir
              -- «bugünün endirimləri» siyahısına BURAXILMIR. Sətir bazada
              -- qalır və admin panelində görünür - orada insan qərar verir.
              AND (pr.flags IS NULL OR pr.flags = '')
            ORDER BY pr.at
            """,
            tuple(markets),
        ).fetchall()

        best: dict[str, dict] = {}
        # Real məhsul fotosu kataloq kəsiyini ƏVƏZ EDİR (M3): kəsik
        # vərəqədən qayçı ilə kəsilmiş parçadır, foto isə məhsulun özü.
        foto = photo_map(conn)
        for row in rows:
            old = float(row["old_price"])
            price = float(row["price"])
            # Cüzi endirim (<3%) atılır. DƏRİN ENDİRİM İSƏ BURADA ATILMIR
            # (`max_depth=None`) - qərar yoxlamadan SONRA verilir (aşağıda).
            # Səbəb: dərinlik özü heç nə sübut etmir; son istifadə tarixi
            # yaxınlaşan məhsul real olaraq 70%+ ucuzlaşa bilər və onu
            # «ağlabatmayan» adlandırmaq istifadəçini ən sərfəli təklifdən
            # uzaqlaşdırmaq deməkdir.
            pct = discount_pct(price, old, max_depth=None)
            if pct is None:
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
                "image": foto.get(row["product_id"], {}).get("url") or image_url(row["image_path"]),
                "image_w": foto.get(row["product_id"], {}).get("w"),
                "image_h": foto.get(row["product_id"], {}).get("h"),
                "store": market.name,
                "store_short": market.short,
                "store_slug": market.slug,
                "price": round(price, 2),
                "old_price": round(old, 2),
                "discount_pct": pct,
                "saving": round(old - price, 2),
                # Yoxlama üçün saxlanılır, cavaba düşmür.
                "_price_id": row["price_id"],
                "_seen_at": row["seen_at"],
                "_store_id": row["store_id"],
            }

        # HƏR ENDİRİM YOXLANILIR - siyahı ilə «endirim yoxlaması» bölməsi
        # eyni funksiyadan qidalanır (`app/analytics.verify_claim`).
        for deal in best.values():
            nəticə = verify_claim(
                conn,
                group_key=deal["group_key"],
                price=deal["price"],
                old_price=deal["old_price"],
                seen_at=deal["_seen_at"],
                price_id=deal["_price_id"],
                store_id=deal["_store_id"],
            )
            deal["verdict"] = nəticə["verdict"]
            deal["verdict_reasons"] = nəticə["reason_keys"]

        # ÇOX DƏRİN ENDİRİM YALNIZ TƏSDİQLƏNMƏYİBSƏ ATILIR.
        #
        # 70%-dən dərin sətir adətən OCR səhvidir (vergül itib, köhnə qiymət
        # yanlış oxunub) - siyahının başında belə zibil dayanmamalıdır.
        # Amma tarixçə iddianı TƏSDİQLƏYİRSƏ, endirim realdır: məhsulu
        # həqiqətən o qiymətə görmüşük. Belə sətri atmaq istifadəçinin
        # tapdığı ən yaxşı təklifi gizlətmək olardı.
        best = {
            açar: deal
            for açar, deal in best.items()
            if deal["discount_pct"] <= MAX_DEPTH * 100 or deal["verdict"] == "tesdiqlenib"
        }

        # SIRA HÖKMƏ GÖRƏDİR, dərinliyə görə yox.
        #
        # Əvvəl siyahı yalnız faizə görə sıralanırdı və ən dərin - yəni ən
        # şübhəli - endirim BİRİNCİ dayanırdı. İstifadəçiyə ən çox güvənilən
        # təklif lazımdır, ən böyük rəqəm yox. İndi: təsdiqlənmiş → yoxlanmamış
        # → şübhəli; hər qrupun içində isə faiz böyükdən kiçiyə.
        # «Hələ az müşahidə» şübhədən YUXARIDIR: o, iddianın yalan olduğunu
        # demir - sadəcə hələ yoxlaya bilmirik.
        RANK = {
            "tesdiqlenib": 0,
            "endirim_yoxdur": 1,
            "az_musahide": 2,
            "tesdiqlenmeyib": 3,
            "subheli": 4,
        }
        ranked = sorted(
            best.values(),
            key=lambda d: (RANK.get(d["verdict"], 3), -d["discount_pct"], d["label"]),
        )[:limit]

        açarlar = [d["group_key"] for d in ranked]
        offers = _offers_by_group(conn, açarlar, markets)
        confidence = match_confidence(conn, açarlar)
        for deal in ranked:
            deal["offers"] = offers.get(deal["group_key"], [])
            deal["compare"] = _compare_note(deal["offers"])
            deal["match"] = confidence.get(deal["group_key"], "exact")
            # ƏHATƏ: neçə marketdə qiymət var / neçə market ümumiyyətlə var.
            # Boş market «tapılmadı» deyil, «hələ datası yoxdur» deməkdir -
            # bu fərq UI-da açıq yazılır.
            # «Cəmi» REYESTRDƏN gəlir (dörd market), bazadakı market sayından
            # yox: Bazar Store və Rahat hələ boşdur, amma istifadəçiyə vəd
            # olunan dörd marketdir. «1/2» yazmaq əhatəni olduğundan yaxşı
            # göstərərdi.
            deal["coverage"] = {"available": len(deal["offers"]), "total": len(MARKETS)}
            for daxili in ("_price_id", "_seen_at", "_store_id"):
                deal.pop(daxili, None)

        return {
            "items": ranked,
            "total_found": len(best),
            "suspicious_depth_pct": round(SUSPICIOUS_DEPTH * 100),
        }
    finally:
        conn.close()


# ------------------------------------------------------------ axtarış / filtr


def _rank_matches(rows, sorğu_tokenləri, fuzzy_namizədlər):
    """
    Nəticələri UYĞUNLUQ PİLLƏSİNƏ görə sıralayır (M1).

    Pillələr `app/search_norm.py`-dədir: 1 tam, 2 söz başlanğıcı, 3 söz
    ortası, 4 bir hərf səhvi.

    DÖRDÜNCÜ PİLLƏ YALNIZ QALAN ÜÇÜ BOŞ QAYIDANDA. SQL alt sətir uyğunluğu
    ilə namizəd verir, yəni bura gələn hər sətir onsuz da 1-3 pilləsindədir.
    Siyahı boşdursa - yazı səhvi ehtimalı var - namizədlər yenidən çəkilir və
    fuzzy açılır. Bu, «süd» sorğusunun «sut/suz» gətirməsinin qarşısını alır:
    dəqiq nəticə varkən fuzzy heç vaxt işə düşmür.

    SIRA DAXİLİNDƏ SQL-in ÖZ SIRASI QORUNUR (market sayı, qiymət): `sorted`
    stabil olduğu üçün eyni pillədəki sətirlər yerini dəyişmir.
    """
    if not sorğu_tokenləri:
        return rows

    ballı = []
    for row in rows:
        bal = match_score(row["name_norm"] or "", sorğu_tokenləri)
        if bal is not None:
            ballı.append((bal, row))

    if not ballı:
        for row in fuzzy_namizədlər():
            bal = match_score(row["name_norm"] or "", sorğu_tokenləri, allow_fuzzy=True)
            if bal is not None:
                ballı.append((bal, row))

    ballı.sort(key=lambda cüt: cüt[0])
    return [row for _, row in ballı]


def search(
    q: str = "",
    market: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 48,
) -> dict:
    """
    Kateqoriya / axtarış nəticələri səhifəsinin datası.

    FİLTRLƏR SÜZGƏCDİR, AXTARIŞ DEYİL: hər biri müstəqil işləyir və boş
    buraxıla bilər. Nəticə həmişə QRUP üzrədir - eyni məhsul iki marketdə
    iki sətir kimi görünməməlidir.

    `facets` sahəsi filtr menyusunu doldurur: hansı kateqoriyalar həqiqətən
    mövcuddur və qiymət aralığı nədir. Sabit siyahı yazsaq, istifadəçi
    nəticəsi olmayan kateqoriyanı seçib boş səhifə alardı.
    """
    conn = get_connection()
    try:
        markets = store_map(conn)
        if not markets:
            return {"items": [], "total": 0, "facets": {"categories": [], "price": None}}

        store_ids = list(markets)
        if market:
            wanted = market_for(market)
            if wanted is None:
                return {"items": [], "total": 0, "facets": {"categories": [], "price": None}}
            store_ids = [sid for sid, m in markets.items() if m.slug == wanted.slug]
            if not store_ids:
                return {"items": [], "total": 0, "facets": {"categories": [], "price": None}}

        where = [f"pr.store_id IN ({','.join('?' * len(store_ids))})"]
        params: list = list(store_ids)

        # AXTARIŞ NORMALLAŞDIRILMIŞ SÜTUN ÜZRƏDİR (M1).
        #
        # Əvvəl şərt `p.name LIKE '%dusbere%'` idi və HEÇ NƏ tapmırdı: bazada
        # ad «düşbərə» kimi yazılıb. İndi hər token `name_norm` sütununda
        # axtarılır - sütun brendi də daxil edir, ona görə «milla sud» kimi
        # çoxsözlü sorğu bir sahədə həll olunur.
        #
        # SQL YALNIZ NAMİZƏD VERİR (alt sətir uyğunluğu). Pillə (tam / söz
        # başlanğıcı / söz ortası) Python-da hesablanır: SQL-də bunu ifadə
        # etmək üç ayrı LIKE və `CASE` deməkdir, oxunmaz olur və indeksdən
        # onsuz da istifadə etmir.
        sorğu_tokenləri = norm_tokens(q)
        for token in sorğu_tokenləri:
            where.append("p.name_norm LIKE ?")
            params.append(f"%{token}%")
        if category:
            where.append("p.category = ?")
            params.append(category)

        # Qiymət filtri QRUPUN ƏN UCUZ qiymətinə görədir (HAVING), çünki
        # istifadəçi «5 manatdan ucuz» deyəndə ödəyəcəyi ən aşağı qiyməti
        # nəzərdə tutur - bahalı marketin qiyməti onu siyahıdan çıxarmamalıdır.
        having = []
        if min_price is not None:
            having.append("MIN(pr.price) >= ?")
        if max_price is not None:
            having.append("MIN(pr.price) <= ?")

        sql = (
            "SELECT p.id AS product_id, p.group_key AS group_key, p.name AS name, "
            "       p.brand AS brand, p.size_value AS size_value, p.size_unit AS size_unit, "
            "       p.category AS category, p.image_path AS image_path, "
            "       p.name_norm AS name_norm, "
            "       MIN(pr.price) AS price, MAX(pr.old_price) AS old_price, "
            "       COUNT(DISTINCT pr.store_id) AS store_count "
            "FROM products p JOIN prices pr ON pr.product_id = p.id "
            f"WHERE {' AND '.join(where)} "
            "GROUP BY p.group_key "
        )
        tail_params = list(params)
        if having:
            sql += f"HAVING {' AND '.join(having)} "
            tail_params += [v for v in (min_price, max_price) if v is not None]
        # Sıralama Python-dadır (aşağıda), ona görə SQL-də limit YOXDUR:
        # limit tətbiq olunsaydı, SQL-in öz sırası ilə kəsilər və uyğunluq
        # pilləsi yüksək olan sətir siyahıdan kənarda qala bilərdi.
        sql += "ORDER BY store_count DESC, price"

        rows = conn.execute(sql, tail_params).fetchall()

        def _sorğusuz_namizədlər():
            """
            Fuzzy keçidi üçün: eyni sorğu, amma AXTARIŞ ŞƏRTİ OLMADAN.

            Yazı səhvi olan token heç bir `LIKE` şərtini ödəmir, ona görə
            namizədləri yenidən çəkmək lazımdır. Digər süzgəclər (market,
            kateqoriya, qiymət) YERİNDƏ QALIR - istifadəçinin seçimi yazı
            səhvinə görə ləğv olunmamalıdır.
            """
            təmiz_where = [ş for ş in where if "name_norm" not in ş]
            təmiz_params = list(store_ids)
            if category:
                təmiz_params.append(category)
            alt_sql = sql.replace(" AND ".join(where), " AND ".join(təmiz_where))
            son_params = təmiz_params + [v for v in (min_price, max_price) if v is not None]
            return conn.execute(alt_sql, son_params).fetchall()

        rows = _rank_matches(rows, sorğu_tokenləri, _sorğusuz_namizədlər)[:limit]

        items = []
        # Real məhsul fotosu kataloq kəsiyini ƏVƏZ EDİR (M3): kəsik
        # vərəqədən qayçı ilə kəsilmiş parçadır, foto isə məhsulun özü.
        foto = photo_map(conn)
        for row in rows:
            price = round(float(row["price"]), 2)
            old = row["old_price"]
            pct = None
            if old and float(old) > price:
                depth = (float(old) - price) / float(old)
                if MIN_DISCOUNT_PCT <= depth * 100 and depth <= MAX_DEPTH:
                    pct = round(depth * 100, 1)
            items.append(
                {
                    "product_id": row["product_id"],
                    "group_key": row["group_key"],
                    "label": display_label(row["name"], row["brand"]),
                    "brand": row["brand"],
                    "size": display_size(row["size_value"], row["size_unit"]),
                    "category": row["category"],
                    "image": foto.get(row["product_id"], {}).get("url") or image_url(row["image_path"]),
                    "image_w": foto.get(row["product_id"], {}).get("w"),
                    "image_h": foto.get(row["product_id"], {}).get("h"),
                    "price": price,
                    "discount_pct": pct,
                    "store_count": row["store_count"],
                }
            )

        # Facet-lər BÜTÜN kataloq üzrədir (cari filtrdən asılı deyil), yəni
        # istifadəçi bir filtri dəyişəndə menyu boşalmır.
        # ==========================================================
        # SAYĞACLAR CARİ NƏTİCƏDƏN GƏLİR, BÜTÜN KATALOQDAN YOX.
        #
        # REAL SƏHVDƏN ÇIXIB: «süd» axtaranda yan paneldə «təmizlik və
        # gigiyena (41)» görünürdü - sayğac bütün bazadan hesablanırdı. Nəticə:
        # istifadəçi nəticəsi OLMAYAN kateqoriyanı seçib boş səhifə alırdı.
        #
        # Şərtlər AÇIQ şəkildə yenidən qurulur: mövcud `where`/`params`
        # siyahılarını süzmək kövrək olardı (hansı parametr hansı şərtə aiddir?).
        #
        # KATEQORİYA FİLTRİ SAYĞACA TƏSİR ETMİR: əks halda bir kateqoriya
        # seçən kimi qalan hamısı menyudan itər və istifadəçi geri qayıda
        # bilməzdi. Qiymət filtri də daxil edilmir - slayderin sərhədləri
        # öz seçimindən asılı olmamalıdır.
        # ==========================================================
        facet_where = [f"pr.store_id IN ({','.join('?' * len(store_ids))})"]
        facet_params: list = list(store_ids)
        for token in sorğu_tokenləri:
            facet_where.append("p.name_norm LIKE ?")
            facet_params.append(f"%{token}%")
        facet_sql = " AND ".join(facet_where)

        cats = conn.execute(
            "SELECT p.category AS category, COUNT(DISTINCT p.group_key) AS n "
            "FROM products p JOIN prices pr ON pr.product_id = p.id "
            f"WHERE {facet_sql} "
            "GROUP BY p.category ORDER BY n DESC",
            tuple(facet_params),
        ).fetchall()
        bounds = conn.execute(
            "SELECT MIN(pr.price) AS lo, MAX(pr.price) AS hi "
            "FROM products p JOIN prices pr ON pr.product_id = p.id "
            f"WHERE {facet_sql}",
            tuple(facet_params),
        ).fetchone()

        return {
            "items": items,
            "total": len(items),
            "facets": {
                "categories": [
                    {"name": r["category"], "count": r["n"]} for r in cats if r["category"]
                ],
                "price": {
                    "min": round(float(bounds["lo"]), 2) if bounds["lo"] is not None else None,
                    "max": round(float(bounds["hi"]), 2) if bounds["hi"] is not None else None,
                },
            },
        }
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
        # HƏR İKİ QAT: kataloq iddiası + mağaza rəf qiyməti. Yalnız `prices`
        # oxunsaydı, Bravonun səhifəsi boş qalardı - onun kataloq mənbəyi
        # yoxdur, bütün qiymətləri mağaza qatındandır.
        rows = conn.execute(
            f"""
            {PRICE_ROWS_CTE}
            SELECT p.id          AS product_id,
                   p.group_key   AS group_key,
                   p.name        AS name,
                   p.brand       AS brand,
                   p.size_value  AS size_value,
                   p.size_unit   AS size_unit,
                   p.category    AS category,
                   p.image_path  AS image_path,
                   pr.price      AS price,
                   pr.old_price  AS old_price,
                   pr.at         AS seen_at
            FROM price_rows pr
            JOIN products p ON p.id = pr.product_id
            WHERE pr.store_id IN ({own_marks})
            ORDER BY pr.at
            """,
            tuple(own_ids),
        ).fetchall()

        # Qrup üzrə ƏN SON müşahidə: `prices` tarixçə saxlayır, market
        # səhifəsində isə cari qiymət göstərilməlidir.
        latest: dict[str, dict] = {}
        # Real məhsul fotosu kataloq kəsiyini ƏVƏZ EDİR (M3): kəsik
        # vərəqədən qayçı ilə kəsilmiş parçadır, foto isə məhsulun özü.
        foto = photo_map(conn)
        for row in rows:
            price = float(row["price"])
            old = float(row["old_price"]) if row["old_price"] is not None else None
            # EYNİ FUNKSİYA, EYNİ HƏDLƏR (`discount_pct`). Əvvəl hesablama
            # burada təkrarlanırdı və «bugünün endirimləri» ilə fərqlənə
            # bilirdi - istifadəçi market səhifəsində «-16%» görüb ana
            # səhifədə həmin məhsulu tapmırdı.
            pct = discount_pct(price, old)

            latest[row["group_key"]] = {
                "product_id": row["product_id"],
                "group_key": row["group_key"],
                "label": display_label(row["name"], row["brand"]),
                "brand": row["brand"],
                "size": display_size(row["size_value"], row["size_unit"]),
                "category": row["category"],
                "image": foto.get(row["product_id"], {}).get("url") or image_url(row["image_path"]),
                "image_w": foto.get(row["product_id"], {}).get("w"),
                "image_h": foto.get(row["product_id"], {}).get("h"),
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
               p.image_path  AS image_path,
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

    # Real məhsul fotosu kataloq kəsiyini ƏVƏZ EDİR (M3).
    foto = photo_map(conn)

    return [
        {
            "product_id": row["product_id"],
            "group_key": row["group_key"],
            "label": display_label(row["name"], row["brand"]),
            "brand": row["brand"],
            "size": display_size(row["size_value"], row["size_unit"]),
            "category": row["category"],
            "image": foto.get(row["product_id"], {}).get("url") or image_url(row["image_path"]),
            "image_w": foto.get(row["product_id"], {}).get("w"),
            "image_h": foto.get(row["product_id"], {}).get("h"),
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


def price_summary(conn: Connection, group_key: str, markets: dict[int, Market]) -> dict | None:
    """
    «Bugünkü qiymət» zolağının datası: ən aşağı ↔ adətən.

    Trolley-də məhsul səhifəsində rəngli zolaq var: solda «Lowest», sağda
    «Usually», üstündə isə cari qiymətin nişanı. Sual sadədir - «bu qiymət
    yaxşıdır, yoxsa adi?».

    ADƏTƏN = MEDİAN, orta yox. Bir dəfəlik dərin endirim ortanı aşağı çəkir
    və nəticədə hər qiymət «adi» görünür; median isə tək müşahidədən
    təsirlənmir.

    İKİ MÜŞAHİDƏDƏN AZ OLANDA None QAYTARILIR: bir dəfə görülmüş qiymətin
    «adətən nə qədər olduğunu» bilmirik və uydurmuruq.
    """
    if not markets:
        return None

    marks = ",".join("?" * len(markets))
    rows = conn.execute(
        f"SELECT pr.price AS price FROM prices pr "
        f"JOIN products p ON p.id = pr.product_id "
        f"WHERE p.group_key = ? AND pr.store_id IN ({marks})",
        (group_key, *markets),
    ).fetchall()

    values = sorted(float(r["price"]) for r in rows)
    if len(values) < 2:
        return None

    lowest = values[0]
    usual = median(values)
    if usual <= lowest:
        # Bütün müşahidələr eynidirsə zolağın iki ucu üst-üstə düşür və
        # nişanın yeri mənasız olur.
        return None

    current = values[0]
    return {
        "lowest": round(lowest, 2),
        "usually": round(usual, 2),
        "current": round(current, 2),
        # Nişanın zolaq üzərindəki mövqeyi (0 = ən ucuz, 100 = adi qiymət).
        "position": round((current - lowest) / (usual - lowest) * 100, 1),
        "observations": len(values),
    }


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
            "       barcode, product_url, image_path "
            "FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row is None:
            return None

        # Real məhsul fotosu kataloq kəsiyini ƏVƏZ EDİR (M3).
        foto = photo_map(conn)

        product = {
            "id": row["id"],
            "image": foto.get(row["id"], {}).get("url") or image_url(row["image_path"]),
            "image_w": foto.get(row["id"], {}).get("w"),
            "image_h": foto.get(row["id"], {}).get("h"),
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

        # OXŞARLIQ İKİ MƏRHƏLƏDİR (P3).
        #
        # SQL yalnız NAMİZƏD verir (eyni kateqoriya), qərarı isə
        # `app/similar.py` verir: ad və brend oxşarlığı. Əvvəl tək şərt
        # kateqoriya idi və «quru ərzaq» qabında düyü ilə salfet yan-yana
        # düşürdü - bölmənin adı «Oxşar məhsullar» olduğu üçün bu, yalan idi.
        #
        # Namizəd limiti 8 deyil, 60-dır: süzgəc ondan sonra işləyir və dar
        # siyahıdan yaxşı uyğunluq çıxmaya bilər.
        namizədlər = _card_rows(
            conn,
            "p.category = ? AND p.group_key != ?",
            (product["category"], product["group_key"]),
            markets,
            60,
        )
        similar = pick_similar(dict(product), namizədlər, limit=8)

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
            # Marketlərarası uyğunluq dəqiqdir, yoxsa təxmini? (A4)
            "match": match_confidence(conn, [product["group_key"]]).get(
                product["group_key"], "exact"
            ),
            # Neçə marketdə qiymət var / dörd marketdən (D18)
            "coverage": {"available": len(offers), "total": len(MARKETS)},
            "price_summary": price_summary(conn, product["group_key"], markets),
            "variants": _variants(conn, product, markets),
            "similar": similar,
            "same_brand": same_brand,
        }
    finally:
        conn.close()
