"""
Qiymət tarixçəsi və endirimin yoxlanması.

"SAXTA ENDİRİM" NƏDİR?
Kataloqda yazılır: "9.99 → 5.99". Amma məhsul heç vaxt 9.99-a satılmayıbsa,
bu, endirim deyil - şişirdilmiş "köhnə qiymət"dir. Marketin öz kataloqundakı
rəqəmə inanmaq üçün səbəb yoxdur; bizim isə ÖZ müşahidələrimiz var.

BİZ NƏ EDƏ BİLƏRİK VƏ NƏ EDƏ BİLMƏRİK:
Biz bir məhsulu neçə dəfə görmüşüksə, o qədər bilirik. Bir dəfə görülmüş
məhsulun "köhnə qiyməti" nə təsdiqlənə, nə də təkzib edilə bilər. Ona görə
hökm ÜÇ deyil, DÖRD haldır və "bilmirik" ayrıca hal kimi saxlanılır:

    tesdiqlenib     - bu qiyməti (və ya ondan yüksəyini) əvvəllər özümüz görmüşük
    tesdiqlenmeyib  - tarixçə yoxdur/azdır; iddianı yoxlaya bilmirik
    subheli         - elan olunan köhnə qiymət indiyədək gördüyümüz ƏN YÜKSƏK
                      qiymətdən xeyli böyükdür, yəni şişirdilmiş görünür
    endirim_yoxdur  - köhnə qiymət göstərilməyib

Niyə "saxta" sözünü hökmdə işlətmirik? Çünki iddia hüquqi məsuliyyət daşıyır,
bizim datamız isə 2-3 kataloqdur. "Şübhəli" dürüst sözdür, "saxta" isə deyil.

İKİNCİ SUAL - ENDİRİM YAXŞIDIRMI?
Endirim həqiqi ola bilər, amma qonşu market elə həmişə daha ucuz satır.
`cheaper_elsewhere` məhz bunu göstərir: "20% endirim var, amma yanındakı
marketdə endirimsiz qiymət daha aşağıdır".
"""

from dataclasses import dataclass, field

from app.db import get_connection
from ingestion.normalize import display_label, display_size

# Elan olunan köhnə qiymət indiyədək gördüyümüz maksimumdan bu qədər dəfə
# böyükdürsə, şişirdilmiş sayılır. 1.25 = 25% marja: qiymətlər həqiqətən
# dəyişir, kiçik fərq şübhə üçün əsas deyil.
INFLATED_RATIO = 1.25

# Tarixçədə bu qiymətin ±5%-i varsa, iddia təsdiqlənmiş sayılır.
# OCR rəqəmi bir qəpik səhv oxuya bilər - dəqiq bərabərlik tələb etmirik.
CONFIRM_TOLERANCE = 0.95

# Ərzaqda bundan dərin endirim praktiki olaraq olmur - ya OCR səhvidir,
# ya da köhnə qiymət uydurmadır.
IMPLAUSIBLE_DEPTH = 0.70

VERDICTS = {
    "tesdiqlenib": "Təsdiqlənib",
    "tesdiqlenmeyib": "Təsdiqlənməyib",
    "subheli": "Şübhəli",
    "endirim_yoxdur": "Endirim yoxdur",
}


@dataclass
class DiscountCheck:
    product_id: int
    group_key: str
    label: str
    store: str
    price: float
    old_price: float | None
    discount_pct: float | None
    verdict: str
    reasons: list[str] = field(default_factory=list)
    observations: int = 0
    max_seen: float | None = None
    cheaper_elsewhere: dict | None = None

    def as_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "group_key": self.group_key,
            "label": self.label,
            "store": self.store,
            "price": round(self.price, 2),
            "old_price": round(self.old_price, 2) if self.old_price else None,
            "discount_pct": self.discount_pct,
            "verdict": self.verdict,
            "verdict_label": VERDICTS.get(self.verdict, self.verdict),
            "reasons": self.reasons,
            "observations": self.observations,
            "max_seen": round(self.max_seen, 2) if self.max_seen else None,
            "cheaper_elsewhere": self.cheaper_elsewhere,
        }


# ---------------------------------------------------------------- tarixçə


def price_history(group_key: str, limit: int = 100) -> dict:
    """
    Bir məhsul qrupunun bütün müşahidələri: hansı marketdə, nə vaxt, neçəyə.

    Niyə group_key? "Süd Milla 1 L" hər marketdə ayrı product_id-dir; qrup
    onları birləşdirir. Qrafik məhz qruplar üzrə mənalıdır.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT pr.price, pr.old_price, pr.unit_price, pr.seen_at, "
            "       s.name AS store, p.name, p.brand, p.size_value, p.size_unit "
            "FROM prices pr "
            "JOIN products p ON p.id = pr.product_id "
            "JOIN stores s ON s.id = pr.store_id "
            "WHERE p.group_key = ? "
            "ORDER BY pr.seen_at, pr.id LIMIT ?",
            (group_key, limit),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"group_key": group_key, "label": group_key, "points": [], "stores": []}

    first = rows[0]
    label = display_label(first["name"], first["brand"])
    size = display_size(first["size_value"], first["size_unit"])

    points = [
        {
            "store": r["store"],
            "price": r["price"],
            "old_price": r["old_price"],
            "unit_price": r["unit_price"],
            "seen_at": r["seen_at"],
        }
        for r in rows
    ]
    return {
        "group_key": group_key,
        "label": label,
        "size": size,
        "points": points,
        "stores": sorted({p["store"] for p in points}),
    }


def tracked_groups(limit: int = 30) -> list[dict]:
    """
    Qrafik üçün seçim siyahısı: ən çox müşahidəsi olan qruplar əvvəldə.

    Niyə sıralama belədir? Bir dəfə görülmüş məhsulun qrafiki tək nöqtədir -
    istifadəçi üçün faydasızdır. Ən çox datası olanı yuxarı qaldırırıq.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT p.group_key, COUNT(pr.id) AS observations, "
            "       COUNT(DISTINCT pr.store_id) AS stores, "
            "       MIN(p.name) AS name, MIN(p.brand) AS brand "
            "FROM products p JOIN prices pr ON pr.product_id = p.id "
            "GROUP BY p.group_key "
            "ORDER BY observations DESC, stores DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "group_key": r["group_key"],
            "label": display_label(r["name"], r["brand"]),
            "observations": r["observations"],
            "stores": r["stores"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------- endirim yoxlaması


def _history_before(conn, group_key: str, seen_at: str, exclude_id: int) -> list[float]:
    """Bu müşahidədən ƏVVƏLKİ qiymətlər - iddianı yalnız keçmişlə yoxlayırıq."""
    rows = conn.execute(
        "SELECT pr.price FROM prices pr JOIN products p ON p.id = pr.product_id "
        "WHERE p.group_key = ? AND pr.id != ? AND pr.seen_at <= ?",
        (group_key, exclude_id, seen_at),
    ).fetchall()
    return [r["price"] for r in rows]


def _cheaper_elsewhere(conn, group_key: str, price: float, store_id: int) -> dict | None:
    """Başqa marketdə həmin qrup daha ucuzdurmu? (ən son qiymətlərlə)"""
    row = conn.execute(
        "SELECT s.name AS store, pr.price FROM prices pr "
        "JOIN products p ON p.id = pr.product_id "
        "JOIN stores s ON s.id = pr.store_id "
        "WHERE p.group_key = ? AND pr.store_id != ? "
        "ORDER BY pr.price ASC LIMIT 1",
        (group_key, store_id),
    ).fetchone()
    if row and row["price"] < price:
        return {"store": row["store"], "price": round(row["price"], 2)}
    return None


def check_discounts(limit: int = 50) -> list[DiscountCheck]:
    """Ən son qiymət sətirlərini bir-bir yoxlayır."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT pr.id, pr.product_id, pr.store_id, pr.price, pr.old_price, "
            "       pr.seen_at, p.group_key, p.name, p.brand, s.name AS store "
            "FROM prices pr "
            "JOIN products p ON p.id = pr.product_id "
            "JOIN stores s ON s.id = pr.store_id "
            "ORDER BY pr.id DESC LIMIT ?",
            (limit,),
        ).fetchall()

        checks: list[DiscountCheck] = []
        for row in rows:
            check = DiscountCheck(
                product_id=row["product_id"],
                group_key=row["group_key"],
                label=display_label(row["name"], row["brand"]),
                store=row["store"],
                price=row["price"],
                old_price=row["old_price"],
                discount_pct=None,
                verdict="endirim_yoxdur",
            )

            check.cheaper_elsewhere = _cheaper_elsewhere(
                conn, row["group_key"], row["price"], row["store_id"]
            )

            if not row["old_price"] or row["old_price"] <= row["price"]:
                checks.append(check)
                continue

            old = row["old_price"]
            check.discount_pct = round((old - row["price"]) / old * 100, 1)

            history = _history_before(conn, row["group_key"], row["seen_at"], row["id"])
            check.observations = len(history)
            check.max_seen = max(history) if history else None

            if check.discount_pct and check.discount_pct >= IMPLAUSIBLE_DEPTH * 100:
                check.verdict = "subheli"
                check.reasons.append(
                    f"Endirim {check.discount_pct}% - ərzaqda bu dərinlikdə "
                    f"endirim praktiki olaraq olmur"
                )
            elif not history:
                check.verdict = "tesdiqlenmeyib"
                check.reasons.append(
                    "Bu məhsulu əvvəllər görməmişik - elan olunan köhnə qiyməti "
                    "yoxlamaq üçün müqayisə nöqtəsi yoxdur"
                )
            elif check.max_seen is not None and old > check.max_seen * INFLATED_RATIO:
                check.verdict = "subheli"
                check.reasons.append(
                    f"Elan olunan köhnə qiymət {old:.2f} AZN, amma indiyədək "
                    f"gördüyümüz ən yüksək qiymət {check.max_seen:.2f} AZN "
                    f"({check.observations} müşahidə)"
                )
            elif check.max_seen is not None and check.max_seen >= old * CONFIRM_TOLERANCE:
                check.verdict = "tesdiqlenib"
                check.reasons.append(
                    f"Bu məhsulu əvvəllər {check.max_seen:.2f} AZN-ə görmüşük - "
                    f"elan olunan köhnə qiymət ({old:.2f}) həqiqətə uyğundur"
                )
            else:
                check.verdict = "tesdiqlenmeyib"
                check.reasons.append(
                    f"Tarixçədə ən yüksək qiymət {check.max_seen:.2f} AZN, "
                    f"iddia isə {old:.2f} AZN - nə təsdiqləyə, nə təkzib edə bilirik"
                )

            if check.cheaper_elsewhere:
                check.reasons.append(
                    f"Endirimdən asılı olmayaraq {check.cheaper_elsewhere['store']} "
                    f"marketində daha ucuzdur: {check.cheaper_elsewhere['price']} AZN"
                )

            checks.append(check)

        return checks
    finally:
        conn.close()


def discount_summary(limit: int = 50) -> dict:
    """Dashboard üçün: hökmlərin sayı + siyahı."""
    checks = check_discounts(limit)
    with_claim = [c for c in checks if c.verdict != "endirim_yoxdur"]

    counts: dict[str, int] = {}
    for check in with_claim:
        counts[check.verdict] = counts.get(check.verdict, 0) + 1

    return {
        "total_checked": len(checks),
        "with_discount_claim": len(with_claim),
        "counts": counts,
        "items": [c.as_dict() for c in with_claim],
    }
