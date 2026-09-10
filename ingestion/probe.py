"""
MƏNBƏ YOXLAMASI — «bağlı market qayıdıbmı?»

PROBLEM: üç marketin mənbəyi ölçülmüş səbəblərlə bağlıdır
(`ingestion/profiles.py`). Bazar Store-un saytı 2026-09-08-dən bəri
«yenilənmə işləri» elanındadır. Vəziyyət nə vaxt dəyişəcək - bilinmir, və
əl ilə yoxlamaq unudulur: sayt qayıdar, biz isə aylarla «mənbə yoxdur»
yazmağa davam edərik.

BU MODUL ÇƏKİLİŞ ETMİR. Yalnız səhifəyə baxıb «burada çəkiləcək bir şey
varmı?» sualına cavab verir və nəticəni `source_probes` cədvəlinə yazır.
Çəkilişin özü `scraper.py`-dədir və vəziyyət dəyişəndə İNSAN qərar verir -
`profiles.py`-dəki `status` avtomatik dəyişmir.

NİYƏ AVTOMATİK STATUS DƏYİŞMİR? `status` ölçülmüş qərardır və izahı ilə
birlikdə kodda yazılır. Robot onu dəyişsəydi, səbəb yazısı köhnə qalardı və
kimsə «niyə active oldu?» sualına cavab tapmazdı. Yoxlama xəbər verir,
qərarı insan verir.

CANLILIQ NECƏ ÖLÇÜLÜR (üç siqnal, hamısı ölçülüb 2026-09-10):

    baxım elanı  - `MAINTENANCE_HINTS` sözlərindən biri mətndədir
    mətn azdır   - Bazarstore baxım səhifəsi cəmi 378 simvol verir;
                   canlı market saytı minlərlə simvol daşıyır
    link yoxdur  - baxım səhifəsində 1 `mailto:` linki var, vəssalam

Üçü də ayrıca yazılır ki, sabah sayt yarımçıq qayıdanda («mətn var, kataloq
yoxdur») fərq görünsün.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

from app.config import settings
from app.db import db_cursor
from ingestion.profiles import profile_for
from ingestion.scraper import find_catalog_links, robots_allows

# Baxım/təmir elanının açar sözləri. Azərbaycanca, rusca və ingiliscə
# variantlar - sayt dil seçiminə görə fərqli mətn verə bilir.
MAINTENANCE_HINTS = (
    "yenilənmə işləri",
    "yenilenme isleri",
    "təmir işləri",
    "baxım",
    "maintenance",
    "under construction",
    "ведутся работы",
    "техническ",
)

# Bundan az mətn = səhifə boşdur. Bazarstore baxım səhifəsi 378 simvol
# verir; canlı market saytı (rahatmarket.az) 2395 simvol verdi. 800 ikisinin
# arasındadır və hər iki tərəfə bol yer buraxır.
MIN_ALIVE_TEXT = 800


@dataclass
class ProbeResult:
    slug: str
    alive: bool = False
    http_status: int | None = None
    text_length: int = 0
    catalog_links: int = 0
    note: str = ""
    signals: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "slug": self.slug,
            "alive": self.alive,
            "http_status": self.http_status,
            "text_length": self.text_length,
            "catalog_links": self.catalog_links,
            "note": self.note,
            "signals": self.signals,
        }


def probe_source(slug: str) -> ProbeResult:
    """
    Marketin mənbə səhifəsinə baxır. Şəbəkə xətası ATMIR.

    Xəta atsaydı, n8n zənciri bir saytın düşməsinə görə tamamilə qırılardı.
    Bunun əvəzinə nəticə `alive=False` və izahlı `note` ilə qayıdır - qeyd
    yenə yazılır və «o gün nə oldu?» sualı cavabsız qalmır.
    """
    profile = profile_for(slug)
    if profile is None:
        return ProbeResult(slug=slug, note="Profil tapılmadı")

    url = profile.page_url or profile.shop_url
    if not url:
        return ProbeResult(slug=slug, note="Yoxlanacaq ünvan yoxdur")

    result = ProbeResult(slug=slug)

    try:
        if not robots_allows(url):
            result.note = "robots.txt qadağan edir"
            result.signals.append("robots")
            return result

        res = requests.get(
            url,
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout_seconds,
        )
        result.http_status = res.status_code
        res.raise_for_status()
        # KODLAŞDIRMA ÖZÜ TƏYİN OLUNUR (ölçüldü: bazarstore.az).
        # `requests` başlıqda charset yoxdursa ISO-8859-1 fərz edir və
        # Azərbaycan hərfləri korlanır: «yenilənmə» -> «yenilÉnmÉ». Nəticədə
        # baxım elanının açar sözü HEÇ VAXT uyğun gəlmirdi - səhv səssiz idi,
        # çünki səhifə yenə oxunurdu, sadəcə hərfləri yanlış idi.
        if not res.encoding or "charset" not in (res.headers.get("content-type") or ""):
            res.encoding = res.apparent_encoding or "utf-8"
    except Exception as e:  # noqa: BLE001 - səbəb qeydə yazılır
        result.note = f"{type(e).__name__}: {e}"[:200]
        result.signals.append("xeta")
        return result

    soup = BeautifulSoup(res.text, "lxml")
    text = soup.get_text(" ", strip=True)
    result.text_length = len(text)
    result.catalog_links = len(find_catalog_links(res.text, url))

    lowered = text.lower()
    if any(hint in lowered for hint in MAINTENANCE_HINTS):
        result.signals.append("baxim_elani")
    if result.text_length < MIN_ALIVE_TEXT:
        result.signals.append("metn_az")
    if result.catalog_links == 0:
        result.signals.append("kataloq_yox")

    # CANLI = baxım elanı YOXDUR **və** (mətn kifayətdir **və ya** kataloq
    # linki var).
    #
    # NİYƏ «VƏ YA»? Ölçüldü: Arazın kataloq səhifəsi client-render-dir və
    # statik HTML-də cəmi 640 simvol mətn verir - yəni mətn həddinə görə
    # «ölü» görünürdü. Halbuki o, layihənin İŞLƏYƏN mənbəyidir və səhifədə
    # 2 kataloq linki var. Kataloq linki mənbənin canlı olmasının ƏN GÜCLÜ
    # sübutudur: çəkiləcək fayl elə odur.
    result.alive = "baxim_elani" not in result.signals and (
        "metn_az" not in result.signals or result.catalog_links > 0
    )

    if result.alive:
        result.note = (
            f"Sayt cavab verir ({result.text_length} simvol, "
            f"{result.catalog_links} kataloq linki)"
        )
    elif "baxim_elani" in result.signals:
        result.note = "Baxım elanı göstərilir"
    else:
        result.note = f"Səhifə demək olar boşdur ({result.text_length} simvol)"
    return result


def record_probe(result: ProbeResult) -> None:
    """
    Nəticəni `source_probes`-a yazır — GÜNDƏ BİR SƏTİR.

    `ON CONFLICT` sayəsində gün ərzində təkrar yoxlama xəta vermir, həmin
    günün sətrini yeniləyir. Bu vacibdir: n8n təkrar cəhd edəndə bütün axın
    IntegrityError ilə qırılmamalıdır.
    """
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO source_probes (slug, alive, http_status, text_length, "
            "                           catalog_links, note) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(slug, date(checked_at)) DO UPDATE SET "
            "  alive = excluded.alive, http_status = excluded.http_status, "
            "  text_length = excluded.text_length, "
            "  catalog_links = excluded.catalog_links, note = excluded.note",
            (
                result.slug,
                1 if result.alive else 0,
                result.http_status,
                result.text_length,
                result.catalog_links,
                result.note,
            ),
        )


def probe_and_record(slug: str) -> ProbeResult:
    """Yoxla + yaz. n8n bu funksiyanı endpoint üzərindən çağırır."""
    result = probe_source(slug)
    record_probe(result)
    return result


def probe_history(slug: str, limit: int = 30) -> list[dict]:
    """Son N günün qeydi — «nə vaxtdan bəri bağlıdır?» sualının cavabı."""
    from app.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT alive, http_status, text_length, catalog_links, note, checked_at "
            "FROM source_probes WHERE slug = ? ORDER BY checked_at DESC LIMIT ?",
            (slug, max(1, min(limit, 365))),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
