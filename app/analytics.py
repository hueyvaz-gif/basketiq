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
from app.stores import display_names, store_filter
from ingestion.normalize import display_label, display_size

# Elan olunan köhnə qiymət indiyədək gördüyümüz maksimumdan bu qədər dəfə
# böyükdürsə, şişirdilmiş sayılır. 1.25 = 25% marja: qiymətlər həqiqətən
# dəyişir, kiçik fərq şübhə üçün əsas deyil.
INFLATED_RATIO = 1.25

# Tarixçədə bu qiymətin ±5%-i varsa, iddia təsdiqlənmiş sayılır.
# OCR rəqəmi bir qəpik səhv oxuya bilər - dəqiq bərabərlik tələb etmirik.
CONFIRM_TOLERANCE = 0.95

# Ərzaqda bundan dərin endirim praktiki olaraq olmur - ya OCR səhvidir,
# ya da köhnə qiymət uydurmadır. Bu hədd SƏRT SÜZGƏCDİR: bundan dərin sətir
# «bugünün endirimləri» siyahısına ümumiyyətlə buraxılmır.
IMPLAUSIBLE_DEPTH = 0.70

# ŞÜBHƏ HƏDDİ - sərt süzgəcdən aşağıdır.
#
# REAL ZİDDİYYƏTDƏN ÇIXIB: «bugünün ən sərfəli endirimləri» −69%-lik sətri
# BİRİNCİ yerdə göstərirdi, «endirim yoxlaması» bölməsi isə eyni dərinliyi
# şübhəli sayırdı. İki bölmə eyni datanı iki cür qiymətləndirirdi - istifadəçi
# hansına inanacağını bilmirdi.
#
# İndi hər iki bölmə EYNİ funksiyadan (`verify_claim`) qidalanır və 55%-dən
# dərin endirim hər yerdə şübhəli sayılır. 55-70% arası sətir siyahıda QALIR,
# amma «yoxlanılmayıb» nişanı ilə və ƏN AŞAĞI sırada.
SUSPICIOUS_DEPTH = 0.55

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
    # Eyni səbəb AÇAR + PARAMETR şəklində. Mətn azərbaycancadır və qalır;
    # brauzer açarı görəndə onu öz dilinə çevirir (`app/static/i18n.js`).
    # Beləcə server dil bilmir, klient isə tərcüməni bir yerdən alır.
    reason_keys: list[dict] = field(default_factory=list)
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
            "reason_keys": self.reason_keys,
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
        # Qrafik də yalnız DÖRD marketi göstərir. Əks halda eyni səhifədə
        # market şəbəkəsi dörd market, qrafik isə beşinci marketin xəttini
        # göstərərdi - istifadəçi üçün bu, izahsız ziddiyyətdir.
        store_clause, store_params = store_filter(conn)
        names = display_names(conn)
        rows = conn.execute(
            "SELECT pr.price, pr.old_price, pr.unit_price, pr.seen_at, pr.store_id, "
            "       p.name, p.brand, p.size_value, p.size_unit "
            "FROM prices pr "
            "JOIN products p ON p.id = pr.product_id "
            f"WHERE p.group_key = ? AND {store_clause} "
            "ORDER BY pr.seen_at, pr.id LIMIT ?",
            (group_key, *store_params, limit),
        ).fetchall()
        rows = [dict(r) | {"store": names[r["store_id"]]} for r in rows]
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
        # Süzgəc olmasaydı, siyahıya yalnız kənar marketdə olan məhsul da
        # düşərdi - istifadəçi onu seçəndə qrafik BOŞ açılardı, çünki
        # `price_history()` həmin marketin sətirlərini onsuz da göstərmir.
        store_clause, store_params = store_filter(conn)
        rows = conn.execute(
            "SELECT p.group_key, COUNT(pr.id) AS observations, "
            "       COUNT(DISTINCT pr.store_id) AS stores, "
            "       MIN(p.name) AS name, MIN(p.brand) AS brand "
            "FROM products p JOIN prices pr ON pr.product_id = p.id "
            f"WHERE {store_clause} "
            "GROUP BY p.group_key "
            "ORDER BY observations DESC, stores DESC LIMIT ?",
            (*store_params, limit),
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
    """
    Başqa marketdə həmin qrup daha ucuzdurmu? (ən son qiymətlərlə)

    «Başqa market» yalnız BİZİM dörd marketimizdən biri ola bilər: istifadəçini
    gedə bilməyəcəyi (və səhifədə göstərilməyən) markete yönləndirmək
    məsləhət deyil, yanıltmadır.
    """
    store_clause, store_params = store_filter(conn)
    names = display_names(conn)
    row = conn.execute(
        "SELECT pr.store_id, pr.price FROM prices pr "
        "JOIN products p ON p.id = pr.product_id "
        f"WHERE p.group_key = ? AND pr.store_id != ? AND {store_clause} "
        "ORDER BY pr.price ASC LIMIT 1",
        (group_key, store_id, *store_params),
    ).fetchone()
    if row and row["price"] < price:
        return {"store": names[row["store_id"]], "price": round(row["price"], 2)}
    return None


def verify_claim(
    conn,
    *,
    group_key: str,
    price: float,
    old_price: float | None,
    seen_at: str,
    price_id: int,
    store_id: int,
) -> dict:
    """
    BİR endirim iddiasını yoxlayır və hökm qaytarır.

    HƏM «endirim yoxlaması» bölməsi, HƏM DƏ «bugünün endirimləri» siyahısı bu
    funksiyanı çağırır. Əvvəl məntiq yalnız yoxlama bölməsində idi və siyahı öz
    ayrıca həddi ilə işləyirdi - nəticədə eyni sətir bir yerdə «ən sərfəli»,
    o biri yerdə «şübhəli» görünürdü.

    Qaytarır: `verdict`, `reasons` (azərbaycanca), `reason_keys` (tərcümə üçün),
    `observations`, `max_seen`, `discount_pct`.
    """
    nəticə = {
        "verdict": "endirim_yoxdur",
        "reasons": [],
        "reason_keys": [],
        "observations": 0,
        "max_seen": None,
        "discount_pct": None,
    }
    if not old_price or old_price <= price:
        return nəticə

    old = float(old_price)
    pct = round((old - price) / old * 100, 1)
    nəticə["discount_pct"] = pct

    history = _history_before(conn, group_key, seen_at, price_id)
    nəticə["observations"] = len(history)
    max_seen = max(history) if history else None
    nəticə["max_seen"] = max_seen

    if pct >= SUSPICIOUS_DEPTH * 100:
        nəticə["verdict"] = "subheli"
        nəticə["reasons"].append(
            f"Endirim {pct}% - ərzaqda bu dərinlikdə endirim praktiki olaraq olmur"
        )
        nəticə["reason_keys"].append({"key": "reason.tooDeep", "params": {"pct": pct}})
    elif not history:
        nəticə["verdict"] = "tesdiqlenmeyib"
        nəticə["reasons"].append(
            "Bu məhsulu əvvəllər görməmişik - elan olunan köhnə qiyməti "
            "yoxlamaq üçün müqayisə nöqtəsi yoxdur"
        )
        nəticə["reason_keys"].append({"key": "reason.neverSeen", "params": {}})
    elif max_seen is not None and old > max_seen * INFLATED_RATIO:
        nəticə["verdict"] = "subheli"
        nəticə["reasons"].append(
            f"Elan olunan köhnə qiymət {old:.2f} AZN, amma indiyədək "
            f"gördüyümüz ən yüksək qiymət {max_seen:.2f} AZN "
            f"({len(history)} müşahidə)"
        )
        nəticə["reason_keys"].append({
            "key": "reason.inflated",
            "params": {"old": f"{old:.2f}", "max": f"{max_seen:.2f}", "n": len(history)},
        })
    elif max_seen is not None and max_seen >= old * CONFIRM_TOLERANCE:
        nəticə["verdict"] = "tesdiqlenib"
        nəticə["reasons"].append(
            f"Bu məhsulu əvvəllər {max_seen:.2f} AZN-ə görmüşük - "
            f"elan olunan köhnə qiymət ({old:.2f}) həqiqətə uyğundur"
        )
        nəticə["reason_keys"].append({
            "key": "reason.confirmed",
            "params": {"max": f"{max_seen:.2f}", "old": f"{old:.2f}"},
        })
    else:
        nəticə["verdict"] = "tesdiqlenmeyib"
        nəticə["reasons"].append(
            f"Tarixçədə ən yüksək qiymət {max_seen:.2f} AZN, "
            f"iddia isə {old:.2f} AZN - nə təsdiqləyə, nə təkzib edə bilirik"
        )
        nəticə["reason_keys"].append({
            "key": "reason.inconclusive",
            "params": {"max": f"{max_seen:.2f}", "old": f"{old:.2f}"},
        })

    return nəticə


def check_discounts(limit: int = 50) -> list[DiscountCheck]:
    """Ən son qiymət sətirlərini bir-bir yoxlayır."""
    conn = get_connection()
    try:
        # Endirim yoxlaması da yalnız dörd marketin iddialarına baxır:
        # bizim satmadığımız marketin kataloqunu yoxlamaq istifadəçiyə
        # heç bir qərar vermir.
        store_clause, store_params = store_filter(conn)
        names = display_names(conn)
        rows = conn.execute(
            "SELECT pr.id, pr.product_id, pr.store_id, pr.price, pr.old_price, "
            "       pr.seen_at, p.group_key, p.name, p.brand "
            "FROM prices pr "
            "JOIN products p ON p.id = pr.product_id "
            f"WHERE {store_clause} "
            "ORDER BY pr.id DESC LIMIT ?",
            (*store_params, limit),
        ).fetchall()
        rows = [dict(r) | {"store": names[r["store_id"]]} for r in rows]

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

            nəticə = verify_claim(
                conn,
                group_key=row["group_key"],
                price=row["price"],
                old_price=row["old_price"],
                seen_at=row["seen_at"],
                price_id=row["id"],
                store_id=row["store_id"],
            )
            check.verdict = nəticə["verdict"]
            check.discount_pct = nəticə["discount_pct"]
            check.observations = nəticə["observations"]
            check.max_seen = nəticə["max_seen"]
            check.reasons = list(nəticə["reasons"])
            check.reason_keys = list(nəticə["reason_keys"])

            if check.discount_pct is None:
                checks.append(check)
                continue

            if check.cheaper_elsewhere:
                check.reasons.append(
                    f"Endirimdən asılı olmayaraq {check.cheaper_elsewhere['store']} "
                    f"marketində daha ucuzdur: {check.cheaper_elsewhere['price']} AZN"
                )
                check.reason_keys.append({
                    "key": "reason.cheaperElsewhere",
                    "params": {
                        "store": check.cheaper_elsewhere["store"],
                        "price": check.cheaper_elsewhere["price"],
                    },
                })

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
