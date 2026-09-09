"""
KARANTİN NÖVBƏSİ — nişanlanmış qiymət sətirlərinin insan baxışı (C12).

`ingestion/quality.py` şübhəli sətri nişanlayır, `app/catalog.py` isə onu
«bugünün endirimləri» siyahısına buraxmır. Amma nişan orada bitsəydi, yoxlama
YARIMÇIQ qalardı: sətir bazada görünməz şəkildə ilişib qalar, heç kim onun
niyə şübhəli sayıldığını bilməzdi və yanlış-müsbətlər (real bahalı məhsul)
həmişəlik gizli qalardı.

Bu modul növbəni ADMİNƏ AÇIR: nə nişanlanıb, hansı səbəbdən, hansı marketdə.

ÜÇ VƏZİYYƏT, İKİ FƏRQLİ «BOŞ»:

    flags = '["deepDiscount"]'   nişanlıdır, ekrana çıxmır, baxış gözləyir
    flags = NULL                 yoxlamadan təmiz keçib
    flags = '' (REVIEWED)        İNSAN baxıb təmiz elan edib

Sonuncu qəsdən ayrıdır. `tools/flag_prices.py` bazanı yenidən yoxlayanda
NULL sətirləri yenidən qiymətləndirir, `''` olanlara isə toxunmur — yoxsa
adminin əl ilə buraxdığı sətir növbəti qaçışda yenidən karantinə düşərdi və
baxış işi mənasız təkrara çevrilərdi.

BİLİNƏN HƏDD: kataloq YENİDƏN emal olunanda `save_products()` həmin kataloqun
qiymət sətirlərini silib yenidən yazır — təsdiq də sətirlə birlikdə gedir.
Bu, qəsdən belədir: yeni emal yeni rəqəmlər gətirir, köhnə qərar isə köhnə
rəqəmlərə aid idi.
"""

from __future__ import annotations

import json

from app.db import db_cursor, get_connection

# «İnsan baxdı, təmizdir» nişanı. Boş sətir seçildi ki, mövcud SQL süzgəci
# (`flags IS NULL OR flags = ''`) dəyişmədən işləsin.
REVIEWED = ""


def _parse(flags: str | None) -> list[str]:
    """Bazadakı JSON mətnini siyahıya çevirir; zədəli dəyər növbəni qırmır."""
    if not flags:
        return []
    try:
        parsed = json.loads(flags)
    except (ValueError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def flagged_prices(limit: int = 50) -> dict:
    """
    Baxış gözləyən sətirlər — ən yenisi başda.

    Sıralama `seen_at` üzrədir: admin adətən SON emalın nəticəsini yoxlayır,
    aylıq köhnə sətri yox.
    """
    limit = max(1, min(limit, 200))
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT pr.id, pr.price, pr.old_price, pr.unit_price, pr.raw_line,
                   pr.flags, pr.seen_at,
                   p.name AS product, p.category, s.name AS store
            FROM prices pr
            JOIN products p ON p.id = pr.product_id
            JOIN stores s ON s.id = pr.store_id
            WHERE pr.flags IS NOT NULL AND pr.flags != ''
            ORDER BY pr.seen_at DESC, pr.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        total = conn.execute(
            "SELECT COUNT(*) FROM prices WHERE flags IS NOT NULL AND flags != ''"
        ).fetchone()[0]
    finally:
        conn.close()

    items = []
    for r in rows:
        old = float(r["old_price"]) if r["old_price"] else None
        price = float(r["price"])
        items.append(
            {
                "price_id": r["id"],
                "product": r["product"],
                "store": r["store"],
                "category": r["category"],
                "price": price,
                "old_price": old,
                # Faiz burada hesablanır, UI-da yox: eyni düsturun iki nüsxəsi
                # olsaydı, biri dəyişəndə digəri səssizcə fərqli rəqəm göstərərdi.
                "discount_pct": round((old - price) / old * 100) if old and old > price else None,
                "unit_price": float(r["unit_price"]) if r["unit_price"] else None,
                "raw_line": r["raw_line"],
                "flags": _parse(r["flags"]),
                "seen_at": r["seen_at"],
            }
        )

    return {"items": items, "total": total}


def approve_price(price_id: int) -> bool:
    """
    Sətri karantindən buraxır: «insan baxdı, təmizdir».

    Nişan SİLİNMİR (NULL edilmir) — `REVIEWED` yazılır ki, yenidən yoxlama
    aləti bu qərarı görsün və sətri təkrar nişanlamasın.

    Qaytarır: sətir tapıldımı.
    """
    with db_cursor() as cur:
        cur.execute(
            "UPDATE prices SET flags = ? WHERE id = ? AND flags IS NOT NULL AND flags != ''",
            (REVIEWED, price_id),
        )
        return cur.rowcount > 0
