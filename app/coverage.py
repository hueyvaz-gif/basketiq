"""
MARKET ƏHATƏSİ (D15) — admin üçün bir cədvəl, dörd sətir.

SUAL SADƏDİR VƏ HƏR GÜN VERİLİR: hansı marketin datası var, nə qədər var,
nə vaxt yenilənib? Əvvəl cavab üç yerə səpələnmişdi - baza sayğacları
(ümumi rəqəm), kataloq siyahısı (fayl adları) və ana səhifədəki «Tezliklə»
yazısı. Heç biri «Bravo-nun datası nə vaxt gəlib?» sualına cavab vermirdi.

ƏHATƏ FAİZİ NƏYƏ GÖRƏ HESABLANIR?
Məxrəc bütün marketlərin BİRLƏŞMİŞ məhsul siyahısıdır (`group_key` üzrə).
Yəni faiz belə oxunur: «saytda tanınan məhsulların neçə faizini bu market
satır?». Mütləq həqiqət deyil - saytda olmayan məhsulu heç bir market üçün
saymırıq - amma müqayisə üçün doğru rəqəmdir: 100% o deməkdir ki, bu marketdə
digərlərində olan hər şey var.

BU SƏHİFƏ HƏM DƏ «MARKETİ AKTİVLƏŞDİRMƏ» YOLUDUR (B9).
Ayrıca düymə yoxdur və qəsdən yoxdur: market datası olan kimi ana səhifədə
avtomatik «işlək» olur (`app/stores.py:market_status`). Əl ilə aktivləşdirmə
düyməsi olsaydı, iki həqiqət yaranardı - «aktiv, amma datasız market» halı
istifadəçiyə boş cədvəl kimi görünərdi.
"""

from __future__ import annotations

from app.db import get_connection
from app.stores import MARKETS, market_for
from ingestion.profiles import profile_for


def store_coverage() -> dict:
    """
    Hər market üçün: məhsul sayı, qiymət sətri sayı, son yenilənmə, əhatə %.

    Reyestrdəki DÖRD marketin hamısı qayıdır - datası olmayan da. Boş market
    cədvəldən düşsəydi, «niyə yoxdur?» sualı yenə cavabsız qalardı.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.slug              AS slug,
                   COUNT(DISTINCT pr.product_id) AS products,
                   COUNT(pr.id)        AS prices,
                   MAX(pr.seen_at)     AS last_seen,
                   COUNT(DISTINCT pr.catalog_id) AS catalogs
            FROM stores s
            LEFT JOIN prices pr ON pr.store_id = s.id
            GROUP BY s.id
            """
        ).fetchall()

        # Məxrəc: bütün marketlərdə tanınan fərqli məhsul (qrup) sayı.
        universe = conn.execute(
            "SELECT COUNT(DISTINCT p.group_key) FROM products p "
            "JOIN prices pr ON pr.product_id = p.id"
        ).fetchone()[0] or 0

        # Marketin ÖZ qrup sayı: `products` sayı deyil. Fərq realdır - eyni
        # məhsul kataloqda iki ölçüdə ola bilər və hər ikisi ayrı `products`
        # sətridir, amma əhatə baxımından bir məhsuldur.
        qruplar = {}
        for row in conn.execute(
            "SELECT s.slug AS slug, COUNT(DISTINCT p.group_key) AS groups "
            "FROM stores s JOIN prices pr ON pr.store_id = s.id "
            "JOIN products p ON p.id = pr.product_id GROUP BY s.id"
        ):
            market = market_for(row["slug"])
            if market:
                qruplar[market.slug] = qruplar.get(market.slug, 0) + row["groups"]
    finally:
        conn.close()

    # Aliaslar birləşdirilir: «araz» və «araz-market» eyni marketdir.
    toplu: dict[str, dict] = {}
    for row in rows:
        market = market_for(row["slug"])
        if market is None:
            continue
        cari = toplu.setdefault(
            market.slug,
            {"products": 0, "prices": 0, "catalogs": 0, "last_seen": None},
        )
        cari["products"] += row["products"] or 0
        cari["prices"] += row["prices"] or 0
        cari["catalogs"] += row["catalogs"] or 0
        # Ən son müşahidə: mətn kimi müqayisə olunur, çünki format
        # `YYYY-MM-DD HH:MM:SS`-dir və leksik sıra zaman sırası ilə üst-üstə düşür.
        if row["last_seen"] and (not cari["last_seen"] or row["last_seen"] > cari["last_seen"]):
            cari["last_seen"] = row["last_seen"]

    items = []
    for market in MARKETS:
        data = toplu.get(market.slug, {"products": 0, "prices": 0, "catalogs": 0, "last_seen": None})
        profile = profile_for(market.slug)
        grup = qruplar.get(market.slug, 0)
        items.append(
            {
                "slug": market.slug,
                "name": market.name,
                "products": data["products"],
                "prices": data["prices"],
                "catalogs": data["catalogs"],
                "last_seen": data["last_seen"],
                "coverage_pct": round(grup / universe * 100) if universe else 0,
                "available": data["products"] > 0,
                # Profil sahələri: admin «niyə boşdur?» sualının cavabını
                # elə həmin sətirdə görür.
                "source_status": profile.status if profile else None,
                "source_format": profile.fmt if profile else None,
                "source_url": profile.page_url if profile else None,
                "source_note": profile.note if profile else "",
            }
        )

    # Dolu market öndə - ana səhifədəki şəbəkə ilə eyni məntiq (B9).
    items.sort(key=lambda m: (not m["available"], -m["products"]))
    return {"items": items, "universe": universe}
