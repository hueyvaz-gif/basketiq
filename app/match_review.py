"""
İNSAN YOXLAMASI NÖVBƏSİ (uyğunlaşdırma, ADDIM 5) — `/admin/matches` üçün data.

NİYƏ AYRICA MODUL? `ai/matcher.py` qərar VERİR; bu modul isə qərarı insana
GÖSTƏRİR: iki məhsulun adı, ölçüsü, şəkli, hansı marketdə neçəyə satıldığı
və kataloqun öz OCR sətri. Bunlar ekran üçündür — uyğunlaşdırma məntiqinə
qarışmamalıdır.

İKİ NÖVBƏ:
  pending — maşın qərar verə bilmədi (ölçü yalnız bir tərəfdə bilinir).
            Real bazada 236 cüt. İnsan baxmasa, heç vaxt birləşməyəcək.
  llm     — LLM qərar verib, insan hələ baxmayıb. Real qaçışda «bəli»lərin
            bir hissəsi ümumi ↔ konkret idi («Aura tualet kağızı» ≡ «...32
            Rulon»), ona görə LLM qərarı son söz sayılmır.
İnsanın cavab verdiyi cüt heç bir növbəyə qayıtmır (`source='human'`).

KATALOQ SƏTRİ NİYƏ GÖSTƏRİLİR? Ölçüsüz kataloq məhsulu («Azərsüd ayran»)
haqqında qərar verən adam OCR mətnində ölçünü çox vaxt görür («ayran 0,5 l
0,89») — maşın onu oxuya bilmədi, göz isə oxuyur.
"""

from __future__ import annotations

import sqlite3

from app.db import PRICE_ROWS_CTE, get_connection
from app.services.product_images import image_url_for
from app.stores import market_for
from ingestion.normalize import display_label, display_size, size_from_name

QUEUES = {
    "pending": "d.decision = 'pending'",
    "llm": "d.source = 'llm'",
}


def queue_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Növbələrin ölçüsü + artıq bağlanmış qərarlar (ekrandakı sayğaclar)."""
    row = conn.execute(
        """
        SELECT SUM(decision = 'pending')                                AS pending,
               SUM(source = 'llm')                                      AS llm,
               SUM(source = 'human')                                    AS human,
               SUM(decision != 'pending' AND source NOT IN ('llm', 'human')) AS auto
          FROM match_decisions
        """
    ).fetchone()
    return {key: row[key] or 0 for key in ("pending", "llm", "human", "auto")}


def _products(conn: sqlite3.Connection, ids: set[int]) -> dict[int, dict]:
    """Kart üçün məhsul + hər marketdə ƏN SON qiyməti (hər iki qatdan)."""
    if not ids:
        return {}
    params = sorted(ids)
    marks = ",".join("?" * len(params))

    out: dict[int, dict] = {}
    for r in conn.execute(
        f"""
        SELECT p.id, p.name, p.brand, p.size_value, p.size_unit, p.category,
               CASE WHEN pi.status = 'ok' THEN pi.image_path END AS image_path
          FROM products p
          LEFT JOIN product_images pi ON pi.product_id = p.id
         WHERE p.id IN ({marks})
        """,
        params,
    ):
        # ÖLÇÜ ADDAN DA OXUNUR. Bravo kartında ölçü çox vaxt adın içindədir
        # («President Kərə Yağı 82% 200qr») və `size_value` boşdur. Onda kart
        # hər iki tərəfdə «ölçü bilinmir» yazırdı - halbuki yalnız KATALOQ
        # tərəfi ölçüsüzdür və insanın görməli olduğu siqnal məhz budur.
        # Qayda `match_key` ilə eynidir (`ingestion/normalize.py`).
        size_value, size_unit = r["size_value"], r["size_unit"]
        if not display_size(size_value, size_unit):
            size_value, size_unit = size_from_name(r["name"])
        out[r["id"]] = {
            "id": r["id"],
            "label": display_label(r["name"], r["brand"]),
            "size": display_size(size_value, size_unit),
            "category": r["category"] or "digər",
            "image": image_url_for(r["image_path"]),
            "offers": [],
        }

    # Sıralama `app/db.py`-dəki qaydadır: at, layer, row_id.
    for r in conn.execute(
        f"""
        {PRICE_ROWS_CTE},
        ranked AS (
            SELECT pr.*, ROW_NUMBER() OVER (
                       PARTITION BY pr.product_id, pr.store_id
                       ORDER BY pr.at DESC, pr.layer DESC, pr.row_id DESC
                   ) AS rn
              FROM price_rows pr
             WHERE pr.product_id IN ({marks})
        )
        SELECT r.product_id, r.price, r.layer, r.at, s.slug, s.name AS store_name, c.raw_line
          FROM ranked r
          JOIN stores s ON s.id = r.store_id
          LEFT JOIN prices c ON r.layer = 'catalog' AND c.id = r.row_id
         WHERE r.rn = 1
         ORDER BY r.price
        """,
        params,
    ):
        market = market_for(r["slug"])
        out[r["product_id"]]["offers"].append({
            "store": market.name if market else r["store_name"],
            "slug": r["slug"],
            "price": r["price"],
            "layer": r["layer"],
            "at": r["at"],
            "raw_line": r["raw_line"],
        })
    return out


def review_queue(status: str = "pending", limit: int = 30) -> dict:
    """Növbədəki cütlər — ən yüksək bal əvvəl (ən çox ehtimal olunan uyğunluq)."""
    if status not in QUEUES:
        raise ValueError(f"naməlum növbə: {status}")
    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT d.a_id, d.b_id, d.decision, d.source, d.similarity, d.reason, d.decided_at
              FROM match_decisions d
             WHERE {QUEUES[status]}
             ORDER BY d.similarity DESC, d.a_id, d.b_id
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
        products = _products(conn, {r["a_id"] for r in rows} | {r["b_id"] for r in rows})
        counts = queue_counts(conn)
    finally:
        conn.close()

    return {
        "status": status,
        "counts": counts,
        "pairs": [
            {
                "a_id": r["a_id"],
                "b_id": r["b_id"],
                "decision": r["decision"],
                "source": r["source"],
                "similarity": r["similarity"],
                "reason": r["reason"],
                "a": products.get(r["a_id"]),
                "b": products.get(r["b_id"]),
            }
            for r in rows
        ],
    }


def pair_state(a_id: int, b_id: int) -> dict | None:
    """İki məhsul mövcuddurmu və indi eyni qrupdadırmı? Yoxdursa None."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, group_key FROM products WHERE id IN (?, ?)", (a_id, b_id)
        ).fetchall()
        if len(rows) != 2:
            return None
        return {"same_group": rows[0]["group_key"] == rows[1]["group_key"],
                "counts": queue_counts(conn)}
    finally:
        conn.close()
