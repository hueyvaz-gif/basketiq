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

import re
from datetime import date
from pathlib import Path

from app.db import db_cursor, get_connection

# Səhifədəki satıla bilən yerlər. Açar = `ads.slot`, dəyər = izah.
SLOTS: dict[str, str] = {
    # Sətir arası banner (market şəbəkəsi ilə «bugünün endirimləri» arasında).
    # HAZIRDA HEÇ BİR SƏHİFƏDƏ YOXDUR: `bd01e6e`-də ana səhifədən götürüldü.
    # Reyestrdə QALIR - köhnə sifarişlər admin cədvəlində görünsün və slot
    # başqa səhifədə yenidən açıla bilsin. Admin forması onu təklif ETMİR
    # (`rendered_slots`), çünki bura yazılan reklam görünməz olardı.
    # AD QISADIR, çünki admin formasındakı seçim qutusunda görünür və uzun
    # mətn kəsilirdi (brauzerdə: «Ana səhifə — marke…»).
    "home-banner": "Ana səhifə — banner",

    # YAN LÖVHƏLƏR (tap.az-dakı düzülüş): məzmunun solunda və sağında şaquli
    # banner. Sətir arası bannerdən FƏRQLİ inventar tipidir - o, axını bir
    # dəfə kəsir, bunlar isə səhifə boyu görünür (sticky).
    #
    # DAR EKRANDA GÖSTƏRİLMİR (`style.css`). Yan lövhə üçün kifayət qədər
    # yer yoxdursa, iki seçim var: məzmunu sıxmaq və ya reklamı gizlətmək.
    # Məzmunu sıxmaq qiymət cədvəlini oxunmaz edir - müqayisə saytında bu,
    # reklam gəlirindən bahalı olardı.
    "home-rail-left": "Ana səhifə — sol lövhə",
    "home-rail-right": "Ana səhifə — sağ lövhə",
}


# SLOT SƏHİFƏDƏ VARMI? (2026-09-11)
#
# REAL TƏLƏDƏN ÇIXIB: `home-banner` səhifədən götürüldü (`bd01e6e`), reyestrdə
# isə qaldı. Admin forması onu «Ana səhifə — banner» kimi təklif etməyə davam
# etdi və istifadəçi sifariş yaratdı: reklam aktiv idi, tarixi düzgün idi,
# API onu qaytarırdı - amma HEÇ BİR səhifə o slotu çəkmirdi (göstərim 0).
#
# NİYƏ İKİNCİ ƏL SİYAHISI YOX? Problem məhz köhnələn siyahıdan yarandı.
# Həqiqət HTML-dədir: `data-slot="..."` olan element varsa, `ads.js` onu
# doldurur. Oxunan elə budur - banner hansısa səhifəyə qayıtsa, forma onu
# özü görər, heç kim reyestri əl ilə yeniləməli olmaz.
_STATIC = Path(__file__).resolve().parent / "static"
_DATA_SLOT = re.compile(r'data-slot="([\w-]+)"')


def rendered_slots() -> set[str]:
    """Hazırda hansısa səhifədə çəkilən slotlar (reyestrlə kəsişmə)."""
    found: set[str] = set()
    for page in _STATIC.glob("*.html"):
        found.update(_DATA_SLOT.findall(page.read_text(encoding="utf-8")))
    return found & set(SLOTS)


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


def ad_target(ad_id: int) -> str | None:
    """Hədəf ünvan - SAYMADAN. Sayğac sönülü olanda (lokal) klik yenə yönləndirməlidir."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT target_url FROM ads WHERE id = ?", (ad_id,)).fetchone()
        return row["target_url"] if row else None
    finally:
        conn.close()


# --------------------------------------------------------------- nümunə sifariş

SAMPLE_IMAGE = "/static/images/ads/sample-banner.svg"
SAMPLE_RAIL_IMAGE = "/static/images/ads/sample-rail.svg"


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
    son = bugün.replace(year=bugün.year + 1).isoformat()

    ilk = create_ad(
        advertiser="Araz Market",
        title="Araz Market — həftənin endirimləri",
        body="Həftəlik kataloqdakı təkliflərə baxın.",
        image_path=SAMPLE_IMAGE,
        target_url="https://arazmarket.az/az/discount-magazine",
        slot="home-banner",
        starts_at=bugün.isoformat(),
        ends_at=son,
        is_sample=True,
    )

    # Yan lövhələr üçün də nümunə: boş slot «xarab görünür», dolu slot isə
    # inventarın necə göründüyünü satıcıya da, istifadəçiyə də göstərir.
    for slot in ("home-rail-left", "home-rail-right"):
        create_ad(
            advertiser="BasketIQ",
            title="Bu lövhə satılır",
            body="Şaquli reklam yeri — səhifə boyu görünür.",
            image_path=SAMPLE_RAIL_IMAGE,
            target_url="/admin",
            slot=slot,
            starts_at=bugün.isoformat(),
            ends_at=son,
            is_sample=True,
        )
    return ilk
