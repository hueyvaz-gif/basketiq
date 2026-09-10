"""
Scraping endpoint-ləri: mənbə siyahısı və "indi çək" əmri.

Bu endpoint həm dashboard düyməsindən, həm də n8n-dən (Həftə 3) çağırılacaq -
ona görə məntiq HTTP-dən asılı deyil, `ingestion/scraper.py`-dədir.

Niyə sinxron (arxa fonda deyil)? Skan PDF-in OCR-ı dəqiqələr çəkir, amma
layihədə növbə sistemi (Celery/Redis) yoxdur - o, 3-cü ayın mövzusu deyil və
tədris dəyəri qatmazdı. Bunun əvəzinə `max_pages` limiti qoyulub: 3 səhifə
~1 dəqiqədir, brauzer də, n8n də bunu gözləyə bilir.
"""

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from app.security import require_admin
from app.stores import market_for
from ingestion.probe import probe_and_record, probe_history
from ingestion.profiles import PROFILES
from ingestion.scraper import SOURCES, ScrapeError, robots_allows, scrape_source

# ADMİN SƏTHİ (B11): panel bağlı olanda bütün endpoint-lər 404 qaytarır.
# Qapı ROUTER səviyyəsindədir - yeni endpoint əlavə edən onu ayrıca
# qorumağı unuda bilməz.
router = APIRouter(prefix="/api/scrape", tags=["scrape"], dependencies=[Depends(require_admin)])


def check_api_key(x_api_key: str | None) -> None:
    """
    Açar YALNIZ production-da tələb olunur.

    Niyə belə? Lokalda dashboard düyməsinin açarı yoxdur və olması da lazım
    deyil - server 127.0.0.1-dədir. DigitalOcean-da isə endpoint internetə
    açıqdır: kimsə onu təkrar-təkrar çağırıb həm bizi, həm market saytını
    yükləyə bilər. Ona görə orada açar məcburidir.
    """
    if not settings.is_production:
        return
    if x_api_key != settings.ingest_api_key:
        raise HTTPException(401, "X-API-Key düzgün deyil")


@router.get("/sources")
def list_sources(check_robots: bool = False):
    """
    Hansı marketlərdən çəkə bilərik?

    check_robots=true olsa hər host üçün robots.txt real olaraq oxunur -
    "icazə hələ də varmı?" sualına cavab. Defolt olaraq söndürülüb, çünki
    bu, şəbəkə sorğusudur və UI-ın açılışını yavaşladar.
    """
    # SİYAHI DÖRD MARKETİN HAMISINI GÖSTƏRİR (D14/D15).
    #
    # Əvvəl yalnız çəkilə bilən mənbə (`SOURCES`) qayıdırdı - admin panelində
    # bir sətir görünürdü və «qalan üç market niyə yoxdur?» sualının cavabı
    # heç yerdə yazılmırdı. İndi hər market öz VƏZİYYƏTİ və ölçülmüş səbəbi
    # ilə görünür; çəkilə bilməyənin düyməsi sadəcə sönük olur.
    out = []
    for slug, profile in PROFILES.items():
        source = SOURCES.get(slug)
        market = market_for(slug)
        item = {
            "key": slug,
            "store": market.name if market else slug,
            "page_url": profile.page_url,
            "note": profile.note,
            "format": profile.fmt,
            "status": profile.status,
            "scrapeable": profile.scrapeable and source is not None,
        }
        if check_robots and profile.page_url:
            try:
                item["robots_allowed"] = robots_allows(profile.page_url)
            except Exception as e:
                item["robots_allowed"] = None
                item["robots_error"] = f"{type(e).__name__}: {e}"
        out.append(item)
    return out


@router.post("/{key}/probe")
def probe_endpoint(
    key: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    «Bu marketin saytı qayıdıbmı?» — yoxlayır və GÜNDƏLİK QEYD yazır.

    NİYƏ ÇƏKİLİŞDƏN AYRI? Çəkiliş yalnız `status=ACTIVE` mənbələr üçün
    mənalıdır. Yoxlama isə məhz BAĞLI mənbələr üçün lazımdır - Bazar Store
    aylarla bağlı qala bilər və dəyişikliyi kimsə görməlidir.

    Vəziyyəti AVTOMATİK dəyişmir: `profiles.py`-dəki `status` ölçülmüş
    qərardır və izahı ilə birlikdə kodda yazılır. Yoxlama xəbər verir,
    qərarı insan verir.
    """
    check_api_key(x_api_key)
    if key not in PROFILES:
        raise HTTPException(404, f"Naməlum mənbə: {key}")

    result = probe_and_record(key)
    payload = result.as_dict()

    # DƏYİŞİKLİK NİŞANI: n8n hesabatı yalnız bunu oxuyub qərar verir.
    # «Hər gün eyni cavab» ilə «bu gün fərqlidir» arasındakı fərq budur.
    profile = PROFILES[key]
    payload["expected_alive"] = profile.status == "active"
    payload["changed"] = result.alive != payload["expected_alive"]
    payload["status"] = profile.status
    return payload


@router.get("/{key}/probe/history")
def probe_history_endpoint(key: str, limit: int = 30):
    """Son N günün yoxlama qeydi - «nə vaxtdan bəri bağlıdır?»."""
    if key not in PROFILES:
        raise HTTPException(404, f"Naməlum mənbə: {key}")
    rows = probe_history(key, limit=limit)
    canli = [r for r in rows if r["alive"]]
    return {
        "slug": key,
        "checks": len(rows),
        "alive_days": len(canli),
        "last_alive": canli[0]["checked_at"] if canli else None,
        "history": rows,
    }


@router.post("/{key}")
def run_scrape(
    key: str,
    max_files: int = 1,
    max_pages: int = 3,
    force_ocr: bool = False,
    psm: int = 0,
    use_selenium: bool = False,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Mənbəni çəkir: səhifə -> kataloq linkləri -> endirmə -> OCR -> DB.

    Qaytarır: tapılan linklər, emal olunanlar, ötürülənlər (təkrar) və xətalar.
    LLM burada İŞƏ DÜŞMÜR - çıxarış ayrıca /api/catalogs/{id}/extract addımıdır.
    Səbəb: əvvəlcə OCR-ın nə oxuduğunu görmək, sonra modeli işə salmaq.
    """
    check_api_key(x_api_key)

    try:
        report = scrape_source(
            key=key,
            max_files=max(1, max_files),
            max_pages=max_pages if max_pages > 0 else None,
            force_ocr=force_ocr,
            psm=psm if psm > 0 else None,
            use_selenium=use_selenium,
        )
    except ScrapeError as e:
        raise HTTPException(400, str(e))

    return report.as_dict()
