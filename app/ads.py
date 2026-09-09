"""
REKLAM SİFARİŞLƏRİ (E19-E24) — satıla bilən yerlər və onların idarəsi.

ÜÇ QAYDA BÜTÜN FAYLA HAKİMDİR:

1. REKLAM HEÇ VAXT ENDİRİM KİMİ GÖRÜNMÜR. Sayt qiymət müqayisəsi vəd edir;
   sponsorlu kart real endirimlə qarışsaydı, saytın yeganə dəyəri - etibar -
   itərdi. Ona görə hər reklam «Reklam» nişanı daşıyır və UI-da ayrı formadadır.

2. YALNIZ AKTİV VƏ VAXTINDA OLAN REKLAM GÖSTƏRİLİR. Bitmiş sifariş öz-özünə
   dayanır - kimsə əl ilə söndürməyi unutsa da, müddəti keçmiş reklam ekranda
   qalmır. Bu, reklamverənə verilən sözün texniki təminatıdır.

3. BOŞ SLOT GİZLƏNMİR, SATILIR. Sifariş yoxdursa, yerə «Sizin reklamınız burada
   ola bilər» yazılır və əlaqə düyməsi qoyulur. Boş yeri gizlətmək inventarı
   görünməz edir; ən yaxşı satıcı elə yerin özüdür.

SLOT ADLARI KODDA SABİTDİR. Bazadan gələn sərbəst mətn səhifədə yeni yer aça
bilməz - əks halda admin panelinə yazılan səhv slot adı reklamı səssizcə
görünməz edərdi (və ya daha pisi: gözlənilməz yerdə göstərərdi).
"""

from __future__ import annotations

from datetime import date

from app.db import db_cursor, get_connection

# Səhifədəki satıla bilən yerlər. Açar = `ads.slot`, dəyər = izah.
SLOTS: dict[str, str] = {
    # Market şəbəkəsi ilə «bugünün endirimləri» arasında. Qəsdən BU yer:
    # istifadəçi marketi seçib endirimlərə keçərkən ora onsuz da baxır,
    # amma axını kəsmir - pop-up deyil, sətir arası kartdır.
    # AD QISADIR, çünki admin formasındakı seçim qutusunda görünür və uzun
    # mətn kəsilirdi (brauzerdə: «Ana səhifə — marke…»). İzah yuxarıdakı
    # şərhdədir - onun yeri koddur, interfeys deyil.
    "home-banner": "Ana səhifə — banner",
}


def _row_to_ad(row) -> dict:
    return {
        "id": row["id"],
        "advertiser": row["advertiser"],
        "title": row["title"],
        "body": row["body"],
        "image": row["image_path"],
        "target_url": row["target_url"],
        "slot": row["slot"],
        "starts_at": row["starts_at"],
        "ends_at": row["ends_at"],
        "active": bool(row["active"]),
        "impressions": row["impressions"],
        "clicks": row["clicks"],
        "is_sample": bool(row["is_sample"]),
    }


def current_ad(slot: str, today: str | None = None) -> dict | None:
    """
    Slotda İNDİ göstəriləcək reklam. Yoxdursa `None` (UI boş vəziyyəti çəkir).

    İki şərt birlikdə: `active` VƏ tarix aralığı. Yalnız birinə baxsaydıq,
    müddəti bitmiş sifariş ekranda qalardı - reklamverən ödəmədiyi günlərdə
    də görünərdi, bu isə həm yanlış, həm də ödənişli müştəriyə haqsızlıqdır.

    Bir slotda bir neçə uyğun sifariş varsa, ƏN SON YARADILAN seçilir: admin
    yeni sifariş yazanda onun dərhal işə düşməsini gözləyir.
    """
    if slot not in SLOTS:
        return None
    bugün = today or date.today().isoformat()

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM ads
            WHERE slot = ? AND active = 1
              AND starts_at <= ? AND ends_at >= ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (slot, bugün, bugün),
        ).fetchone()
    finally:
        conn.close()

    return _row_to_ad(row) if row else None


def list_ads() -> list[dict]:
    """Admin siyahısı: bütün sifarişlər, ən yenisi başda."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM ads ORDER BY created_at DESC, id DESC").fetchall()
    finally:
        conn.close()
    return [_row_to_ad(r) for r in rows]


def create_ad(
    *,
    advertiser: str,
    title: str,
    target_url: str,
    slot: str,
    starts_at: str,
    ends_at: str,
    body: str = "",
    image_path: str | None = None,
    active: bool = True,
    is_sample: bool = False,
) -> int:
    """Yeni sifariş yaradır və id-sini qaytarır."""
    if slot not in SLOTS:
        raise ValueError(f"Naməlum slot: '{slot}'. Mövcud: {', '.join(SLOTS)}")
    if ends_at < starts_at:
        raise ValueError("Bitmə tarixi başlanğıcdan əvvəl ola bilməz")

    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO ads (advertiser, title, body, image_path, target_url, slot, "
            "                 starts_at, ends_at, active, is_sample) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                advertiser.strip(),
                title.strip(),
                body.strip(),
                image_path,
                target_url.strip(),
                slot,
                starts_at,
                ends_at,
                int(active),
                int(is_sample),
            ),
        )
        return cur.lastrowid


# Admin panelindən dəyişdirilə bilən sahələr. Siyahı QAPALIDIR: `impressions`
# və `clicks` bura DÜŞMÜR - hesabat rəqəmini əl ilə redaktə etmək imkanı
# hesabatın özünü mənasız edərdi.
YENİLƏNƏ_BİLƏN = (
    "advertiser", "title", "body", "image_path", "target_url",
    "slot", "starts_at", "ends_at", "active",
)


def update_ad(ad_id: int, **fields) -> bool:
    """Sifarişi yeniləyir. Tanınmayan sahə səssizcə atılmır - xəta verir."""
    naməlum = set(fields) - set(YENİLƏNƏ_BİLƏN)
    if naməlum:
        raise ValueError(f"Dəyişdirilə bilməyən sahə: {', '.join(sorted(naməlum))}")
    if not fields:
        return False
    if "slot" in fields and fields["slot"] not in SLOTS:
        raise ValueError(f"Naməlum slot: '{fields['slot']}'")

    if "active" in fields:
        fields["active"] = int(bool(fields["active"]))

    sütunlar = ", ".join(f"{ad} = ?" for ad in fields)
    with db_cursor() as cur:
        cur.execute(f"UPDATE ads SET {sütunlar} WHERE id = ?", (*fields.values(), ad_id))
        return cur.rowcount > 0


def delete_ad(ad_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
        return cur.rowcount > 0


def record_impression(ad_id: int) -> None:
    """
    Göstərim sayğacı: reklam SERVERƏ SORUŞULANDA artır.

    DÜRÜST AD «göstərilmək üçün göndərildi»dir - istifadəçinin ekranında
    həqiqətən görünüb-görünmədiyini yalnız görünmə müşahidəçisi (Intersection
    Observer) deyə bilər. Rəqəmi belə adlandırmaq reklamverəni yanıltmamaq
    üçündür; admin panelində də «göstərim» kimi izah olunur.
    """
    with db_cursor() as cur:
        cur.execute("UPDATE ads SET impressions = impressions + 1 WHERE id = ?", (ad_id,))


def record_click(ad_id: int) -> str | None:
    """Klik sayğacını artırır və hədəf ünvanı qaytarır (yoxdursa `None`)."""
    with db_cursor() as cur:
        cur.execute("UPDATE ads SET clicks = clicks + 1 WHERE id = ?", (ad_id,))
        if cur.rowcount == 0:
            return None
        cur.execute("SELECT target_url FROM ads WHERE id = ?", (ad_id,))
        row = cur.fetchone()
        return row["target_url"] if row else None


# --------------------------------------------------------------- nümunə sifariş

SAMPLE_IMAGE = "/static/images/ads/sample-banner.svg"


def seed_sample_ad() -> int | None:
    """
    NÜMUNƏ sifariş (E24) — slot boş görünməsin deyə bir canlı nümunə.

    NİYƏ `is_sample` SÜTUNU VAR? Bu, real satış deyil. Nişan olmasaydı,
    hesabatda nümunə sifariş ödənişli müştəri kimi sayılardı və «reklamımız
    neçə klik aldı?» sualının cavabı yanlış çıxardı.

    İDEMPOTENTDİR: baza artıq reklam saxlayırsa, heç nə əlavə olunmur - yəni
    admin nümunəni silsə, o, növbəti başlanğıcda geri qayıtmır.
    """
    conn = get_connection()
    try:
        if conn.execute("SELECT 1 FROM ads LIMIT 1").fetchone():
            return None
    finally:
        conn.close()

    bugün = date.today()
    return create_ad(
        advertiser="Araz Market",
        title="Araz Market — həftənin endirimləri",
        body="Həftəlik kataloqdakı təkliflərə baxın.",
        image_path=SAMPLE_IMAGE,
        target_url="https://arazmarket.az/az/discount-magazine",
        slot="home-banner",
        starts_at=bugün.isoformat(),
        ends_at=bugün.replace(year=bugün.year + 1).isoformat(),
        is_sample=True,
    )
