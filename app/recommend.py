"""
Profil əsaslı tövsiyə.

`compare()` sualı belədir: "hansı market ucuzdur?"
Bu modulun sualı isə başqadır: "MƏNƏ nə etmək sərfəlidir?"

Fərq praktikdir. Ən ucuz market hər zaman doğru cavab deyil:

  - Səbəti iki markete bölmək cəmi 0.40 AZN qənaət edirsə, avtomobili
    olmayan adam üçün bu, tövsiyə deyil - vaxt itkisidir.
  - 5 nəfərlik ailəyə 1 litrlik süd yox, 2 litrlik almaq sərfəlidir -
    çünki litrin qiyməti aşağıdır. Tək yaşayan üçün isə əksinə: böyük
    qablaşdırma xarab olur.
  - Büdcəsi 60 AZN olan adama "səbət 78 AZN" demək azdır; hansı 3 məhsulun
    büdcəni yediyini göstərmək lazımdır.

Ona görə burada rəqəmlər PROFİLƏ görə şərh olunur. Rəqəmlərin özü yenə də
Python-da hesablanır - LLM heç nə hesablamır (bax: ai/advisor.py).
"""

import re
from dataclasses import dataclass, field

from app.db import get_connection
from app.profile import Profile, get_profile
from ingestion.normalize import display_label

# canonical_key-in sonundakı ölçü hissəsi: "1l", "0.5kg", "12pcs"
_SIZE_SEGMENT = re.compile(r"^\d+(\.\d+)?(kg|l|pcs)$")

# Böyük qablaşdırma tövsiyəsi bu ailə ölçüsündən başlayır.
# Niyə 3? 1-2 nəfərlik evdə böyük qablaşdırma çox vaxt xarab olur -
# qənaət kağız üzərində qalır.
BULK_MIN_HOUSEHOLD = 3

# Vahid qiymətdə bundan kiçik fərq tövsiyə üçün əsas deyil (OCR səhvi ola bilər).
BULK_MIN_GAIN_PCT = 8.0


@dataclass
class Recommendation:
    plan: str = "yoxdur"              # tek_market | bolunmus | yoxdur
    stores: list[str] = field(default_factory=list)
    total: float | None = None
    single_total: float | None = None
    split_total: float | None = None
    split_saving: float | None = None
    assignments: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    budget: dict | None = None
    bulk_tips: list[dict] = field(default_factory=list)
    profile: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "plan": self.plan,
            "stores": self.stores,
            "total": round(self.total, 2) if self.total is not None else None,
            "single_total": round(self.single_total, 2) if self.single_total else None,
            "split_total": round(self.split_total, 2) if self.split_total else None,
            "split_saving": round(self.split_saving, 2) if self.split_saving else None,
            "assignments": self.assignments,
            "notes": self.notes,
            "warnings": self.warnings,
            "budget": self.budget,
            "bulk_tips": self.bulk_tips,
            "profile": self.profile,
        }


def base_name_key(canonical_key: str) -> str:
    """
    'milla|sud|1l' -> 'milla|sud'

    Ölçüsüz açar eyni məhsulun fərqli qablaşdırmalarını tapmağa imkan verir.
    canonical_key ölçünü SONUNCU seqment kimi saxlayır (bax: normalize.py).
    """
    parts = canonical_key.split("|")
    if len(parts) > 1 and _SIZE_SEGMENT.match(parts[-1]):
        return "|".join(parts[:-1])
    return canonical_key


def _bulk_alternatives(labels: dict[str, str]) -> list[dict]:
    """
    Eyni məhsulun daha sərfəli qablaşdırması varmı?

    Müqayisə VAHİD QİYMƏT üzərindədir (1 kq / 1 L), çünki 2 litrlik südün
    mütləq qiyməti həmişə böyükdür - sual "litri neçəyədir?" olmalıdır.
    """
    if not labels:
        return []

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT p.canonical_key, p.name, p.brand, p.size_value, p.size_unit, "
            "       MIN(pr.unit_price) AS unit_price, s.name AS store "
            "FROM products p "
            "JOIN prices pr ON pr.product_id = p.id "
            "JOIN stores s ON s.id = pr.store_id "
            "WHERE pr.unit_price IS NOT NULL "
            "GROUP BY p.canonical_key"
        ).fetchall()
    finally:
        conn.close()

    by_base: dict[str, list[dict]] = {}
    for row in rows:
        base = base_name_key(row["canonical_key"])
        by_base.setdefault(base, []).append(
            {
                "canonical_key": row["canonical_key"],
                "label": display_label(row["name"], row["brand"]),
                "size_value": row["size_value"],
                "size_unit": row["size_unit"],
                "unit_price": row["unit_price"],
                "store": row["store"],
            }
        )

    tips = []
    for canonical_key, label in labels.items():
        base = base_name_key(canonical_key)
        options = by_base.get(base, [])
        if len(options) < 2:
            continue

        current = next(
            (o for o in options if o["canonical_key"] == canonical_key), None
        )
        if current is None or not current["unit_price"]:
            continue

        best = min(options, key=lambda o: o["unit_price"])
        if best["canonical_key"] == canonical_key:
            continue

        gain = (current["unit_price"] - best["unit_price"]) / current["unit_price"] * 100
        if gain < BULK_MIN_GAIN_PCT:
            continue
        # Yalnız DAHA BÖYÜK qablaşdırma tövsiyə olunur
        if not (best["size_value"] and current["size_value"]):
            continue
        if best["size_value"] <= current["size_value"]:
            continue

        tips.append(
            {
                "current": label,
                "current_unit_price": round(current["unit_price"], 2),
                "better": best["label"],
                "better_size": f"{best['size_value']:g} {best['size_unit']}",
                "better_unit_price": round(best["unit_price"], 2),
                "gain_pct": round(gain, 1),
                "store": best["store"],
            }
        )

    return tips


def recommend(compare_data: dict, profile: Profile | None = None) -> Recommendation:
    """
    Müqayisə nəticəsi + profil -> konkret tövsiyə.

    `compare_data` app/api/basket.py:compare() çıxışıdır. Onu burada yenidən
    hesablamırıq - "natamam market qalib elan edilmir" qaydası orada bir dəfə
    yazılıb və iki nüsxə olmamalıdır.
    """
    profile = profile or get_profile()
    rec = Recommendation(profile=profile.as_dict())
    items = compare_data.get("items", [])

    if not items:
        rec.notes.append("Səbət boşdur.")
        return rec

    stores = {s["store_id"]: s for s in compare_data.get("stores", [])}
    best = compare_data.get("best")

    # --- 1. Tək market variantı -------------------------------------------
    if best:
        rec.single_total = best["total"]

    # --- 2. Bölünmüş variant: hər məhsulu ən ucuz marketdən ----------------
    split_total = 0.0
    split_stores: set[int] = set()
    assignments: list[dict] = []
    covered = 0

    for item in items:
        prices = item.get("prices") or {}
        if not prices:
            assignments.append({"label": item["label"], "store": None, "price": None})
            continue
        cheapest_id = min(prices, key=lambda sid: prices[sid]["price"])
        price = prices[cheapest_id]["price"] * item["qty"]
        split_total += price
        split_stores.add(int(cheapest_id))
        covered += 1
        assignments.append(
            {
                "label": item["label"],
                "store": stores.get(int(cheapest_id), {}).get("store"),
                "price": round(price, 2),
            }
        )

    complete_split = covered == len(items)
    if complete_split:
        rec.split_total = split_total

    # --- 3. Profilə görə plan seçimi --------------------------------------
    if not best and not complete_split:
        rec.notes.append(
            "Heç bir market səbətin hamısını satmır və məhsulların bir hissəsi "
            "ümumiyyətlə tapılmadı - tam plan qurmaq mümkün deyil."
        )
        return rec

    if profile.max_stores <= 1:
        if best:
            rec.plan = "tek_market"
            rec.stores = [best["store"]]
            rec.total = best["total"]
            rec.notes.append(
                f"Profilə görə yalnız bir markete gedirsən - {best['store']} seçildi."
            )
            if complete_split and split_total < best["total"]:
                lost = best["total"] - split_total
                rec.notes.append(
                    f"Səbəti {len(split_stores)} markete bölsən {lost:.2f} AZN "
                    f"qənaət edərdin - profildə 'neçə market' dəyərini artıra bilərsən."
                )
        else:
            rec.notes.append(
                "Heç bir market səbətin hamısını satmır, profil isə tək market "
                "tələb edir - ya profili dəyiş, ya səbətdən məhsul çıxar."
            )
            return rec
    else:
        saving = (best["total"] - split_total) if (best and complete_split) else None
        # Qənaəti hansı plan seçilməsindən ASILI OLMAYARAQ göstəririk -
        # istifadəçi "nə itirirəm?" sualının cavabını görməlidir.
        rec.split_saving = saving
        can_split = complete_split and len(split_stores) <= profile.max_stores

        if can_split and (saving is None or saving >= profile.min_split_saving):
            rec.plan = "bolunmus"
            rec.stores = sorted(
                {a["store"] for a in assignments if a["store"]}
            )
            rec.total = split_total
            rec.assignments = assignments
            if saving:
                rec.notes.append(
                    f"Səbəti {len(rec.stores)} markete bölmək {saving:.2f} AZN "
                    f"qənaət edir - profildəki hədddən ({profile.min_split_saving:.2f} AZN) çoxdur."
                )
        elif best:
            rec.plan = "tek_market"
            rec.stores = [best["store"]]
            rec.total = best["total"]
            # Səbəbi DƏQİQ yazmaq lazımdır. İki fərqli səbəb var və onları
            # qarışdırsaq, istifadəçi yanlış ayarı dəyişməyə çalışar:
            # "qənaət azdır" -> hədd; "çox market lazımdır" -> market sayı.
            if complete_split and len(split_stores) > profile.max_stores:
                rec.notes.append(
                    f"Bölünmüş plan {len(split_stores)} market tələb edir, "
                    f"profil isə {profile.max_stores} markete icazə verir."
                )
            elif saving is not None:
                rec.notes.append(
                    f"Bölmək cəmi {saving:.2f} AZN qənaət edir - profildəki "
                    f"həddən ({profile.min_split_saving:.2f} AZN) azdır, "
                    f"ona görə tək market tövsiyə olunur."
                )
        else:
            rec.plan = "bolunmus"
            rec.stores = sorted({a["store"] for a in assignments if a["store"]})
            rec.total = split_total
            rec.assignments = assignments
            rec.notes.append(
                "Heç bir market səbətin hamısını satmır - məhsullar marketlər "
                "arasında bölünüb."
            )

    # --- 4. Büdcə ----------------------------------------------------------
    if profile.weekly_budget and rec.total is not None:
        over = rec.total - profile.weekly_budget
        rec.budget = {
            "limit": profile.weekly_budget,
            "total": round(rec.total, 2),
            "over": round(over, 2) if over > 0 else 0.0,
            "fits": over <= 0,
        }
        if over > 0:
            expensive = sorted(
                (a for a in assignments if a.get("price")),
                key=lambda a: a["price"],
                reverse=True,
            )[:3]
            rec.budget["biggest_items"] = expensive
            names = ", ".join(a["label"] for a in expensive)
            rec.warnings.append(
                f"Səbət büdcəni {over:.2f} AZN aşır. Ən böyük paylar: {names}."
            )

    # --- 5. Ailə ölçüsü: böyük qablaşdırma ---------------------------------
    if profile.household_size >= BULK_MIN_HOUSEHOLD and profile.prefer_unit_price:
        labels = {}
        conn = get_connection()
        try:
            for item in items:
                row = conn.execute(
                    "SELECT canonical_key, name, brand FROM products WHERE id = ?",
                    (item["product_id"],),
                ).fetchone()
                if row:
                    labels[row["canonical_key"]] = display_label(
                        row["name"], row["brand"]
                    )
        finally:
            conn.close()

        rec.bulk_tips = _bulk_alternatives(labels)
        for tip in rec.bulk_tips:
            rec.notes.append(
                f"{profile.household_size} nəfərlik ev üçün '{tip['better']}' "
                f"({tip['better_size']}) daha sərfəlidir: vahid qiymət "
                f"{tip['better_unit_price']} AZN, indikindən {tip['gain_pct']}% aşağı."
            )

    # --- 6. İstənilməyən məhsullar -----------------------------------------
    if profile.avoid:
        hits = [
            item["label"]
            for item in items
            if any(word in item["label"].lower() for word in profile.avoid)
        ]
        if hits:
            rec.warnings.append(
                "Profilində istəmədiyin sözlər var, amma səbətdə bu məhsullar "
                "qalıb: " + ", ".join(hits)
            )

    return rec
