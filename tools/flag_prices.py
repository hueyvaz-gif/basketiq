"""
Bazadakı qiymət sətirlərini sağlamlıq yoxlamasından keçirir və nişanlayır.

    python -m tools.flag_prices           # nə nişanlanacağını göstərir
    python -m tools.flag_prices --apply   # bazaya yazır

NİYƏ AYRICA ALƏT?
Yoxlama emal zəncirinə qoşulub (`ingestion/pipeline.py`), yəni YENİ sətirlər
avtomatik nişanlanır. Amma bazada onsuz da minlərlə köhnə sətir var - onları
yenidən emal etmək OCR və LLM deməkdir. Bu alət yalnız RƏQƏMLƏRƏ baxır:
qiymət, köhnə qiymət, vahid qiyməti və tarixçə. Model çağırılmır.

HƏDLƏR VƏ İZAHLARI: `ingestion/quality.py`.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from statistics import median

from app.db import get_connection
from app.review import REVIEWED
from ingestion.quality import check_price


def _base_unit(size_unit: str | None) -> str:
    """`g`/`kg` -> kq · `ml`/`l` -> l · `pcs` -> ədəd. Vahid növü qrupudur."""
    if size_unit in ("kg", "g"):
        return "kg"
    if size_unit in ("l", "ml"):
        return "l"
    if size_unit == "pcs":
        return "pcs"
    return "?"


def collect() -> tuple[list[tuple[int, list[str]]], Counter]:
    """Hər sətir üçün bayraqları hesablayır. Bazaya YAZMIR."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT pr.id, pr.price, pr.old_price, pr.unit_price, pr.seen_at, pr.flags, "
            "       p.group_key, p.category, p.size_unit "
            "FROM prices pr JOIN products p ON p.id = pr.product_id "
            "ORDER BY pr.id"
        ).fetchall()

        # Məhsulun tarixçəsi: eyni qrupun BAŞQA sətirləri.
        by_group: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            by_group[r["group_key"]].append(float(r["price"]))

        # Kateqoriya norması (kateqoriya + VAHİD NÖVÜ üzrə).
        #
        # REAL YANLIŞ-MÜSBƏTDƏN ÇIXIB: əvvəl norma yalnız kateqoriya üzrə idi
        # və «₼/ədəd» ilə «₼/kq» eyni qaba düşürdü. Nəticə: yumurta (0.24/ədəd),
        # salfet (0.01/ədəd), tualet kağızı (0.41/ədəd) — hamısı «kənarlaşma»
        # kimi nişanlanırdı, halbuki qiymətləri tamamilə normaldır.
        # İndi ₼/kq yalnız ₼/kq ilə müqayisə olunur.
        by_norm: dict[tuple[str, str], list[float]] = defaultdict(list)
        for r in rows:
            if r["unit_price"]:
                by_norm[(r["category"] or "digər", _base_unit(r["size_unit"]))].append(
                    float(r["unit_price"])
                )
        category_median = {
            açar: median(values) for açar, values in by_norm.items() if len(values) >= 5
        }

        nəticə: list[tuple[int, list[str]]] = []
        sayğac: Counter = Counter()
        for r in rows:
            # ADMİNİN QƏRARI GERİ QAYTARILMIR. Boş sətir (`REVIEWED`) «insan
            # baxdı, təmizdir» deməkdir; onu yenidən qiymətləndirsək, hər
            # qaçışda eyni sətir karantinə qayıdar və baxış işi mənasız
            # təkrara çevrilərdi. NULL isə «hələ yoxlanmayıb» deməkdir.
            if r["flags"] == REVIEWED:
                sayğac["reviewed"] += 1
                continue

            tarixçə = [v for v in by_group[r["group_key"]] if v != float(r["price"])]
            flags = check_price(
                price=float(r["price"]),
                old_price=float(r["old_price"]) if r["old_price"] else None,
                history=tarixçə,
                unit_price=float(r["unit_price"]) if r["unit_price"] else None,
                category_median_unit=category_median.get(
                    (r["category"] or "digər", _base_unit(r["size_unit"]))
                ),
            )
            nəticə.append((r["id"], flags))
            for f in flags:
                sayğac[f] += 1
        return nəticə, sayğac
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Qiymət sətirlərini nişanlayır")
    parser.add_argument("--apply", action="store_true", help="bazaya yaz")
    args = parser.parse_args()

    nəticə, sayğac = collect()
    nişanlı = [(pid, f) for pid, f in nəticə if f]

    print(f"Yoxlanıldı: {len(nəticə)} sətir · nişanlandı: {len(nişanlı)}")
    if sayğac.get("reviewed"):
        print(f"  {'(admin təsdiqi)':16} {sayğac['reviewed']} sətrə toxunulmadı")
    for ad, say in sayğac.most_common():
        if ad == "reviewed":   # bayraq deyil, atlanan sətir sayıdır
            continue
        print(f"  {ad:16} {say}")

    if not args.apply:
        print("\nBu, yalnız ÖN BAXIŞDIR. Yazmaq üçün: --apply")
        return 0

    conn = get_connection()
    try:
        for pid, flags in nəticə:
            conn.execute(
                "UPDATE prices SET flags = ? WHERE id = ?",
                (json.dumps(flags) if flags else None, pid),
            )
        conn.commit()
    finally:
        conn.close()
    print(f"\nYazıldı: {len(nişanlı)} sətir nişanlandı, {len(nəticə) - len(nişanlı)} təmiz.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
