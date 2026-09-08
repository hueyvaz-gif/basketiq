"""
FastAPI giriş nöqtəsi.

İşə salmaq:  uvicorn app.main:app --reload
Dashboard:   http://localhost:8000
Sağlamlıq:   http://localhost:8000/health
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai.llm import check_llm
from app.api import (
    analytics,
    basket,
    catalog,
    catalogs,
    match,
    products,
    profile,
    scrape,
    voice,
)
from mcp_server.server import http_app as mcp_http_app
from app.config import settings
from app.db import db_stats, init_db
from app.models import HealthResponse

STATIC_DIR = settings.base_dir / "app" / "static"

# Statik fayllar dəyişəndə brauzer BUNU DƏRHAL GÖRMƏLİDİR.
#
# NİYƏ AYRICA SİNİF LAZIM OLDU? Real problemdən çıxıb: CSS və JS yenilənəndən
# sonra səhifə brauzerdə DƏYİŞMİRDİ. Səbəb `Cache-Control` başlığının
# ÜMUMİYYƏTLƏ göndərilməməsi idi. FastAPI-nin `StaticFiles`-i yalnız `etag` və
# `last-modified` verir; belə cavabda brauzer "evristik keşləmə" tətbiq edir -
# yəni faylı serverdən SORUŞMADAN köhnə nüsxədən götürür. Nəticə: sən kodu
# dəyişirsən, F5 basırsan, heç nə olmur; yalnız Ctrl+Shift+R kömək edir.
#
# `no-cache` "keşləmə" DEMƏK DEYİL - "hər dəfə soruş" deməkdir. Fayl
# dəyişməyibsə server 304 qaytarır və heç bir bayt ötürülmür, yəni sürət itmir.
#
# Production-da daha yaxşı yol fayl adına versiya yazmaqdır
# (`style.a1b2c3.css` + `max-age=31536000`), amma bu, build addımı tələb edir.
# Bu layihədə build addımı yoxdur, ona görə düzgün seçim `no-cache`-dir.
NO_CACHE = "no-cache, must-revalidate"


class RevalidatedStaticFiles(StaticFiles):
    """Hər statik cavaba `Cache-Control: no-cache` əlavə edir."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = NO_CACHE
        return response

class _MCPProxy:
    """
    /mcp ünvanına gələn sorğunu HAZIRDA aktiv olan MCP tətbiqinə ötürür.

    Niyə proxy? MCP-nin sessiya meneceri bir nüsxədə YALNIZ BİR DƏFƏ işə salına
    bilir ("run() can only be called once per instance"). Tətbiqi modul
    səviyyəsində bir dəfə yaratsaq, server ikinci dəfə qalxanda (testlərdə hər
    TestClient yeni lifespan açır) həmin xəta ilə qırılır.

    Ona görə mount olunan obyekt sabit qalır, arxasındakı MCP tətbiqi isə hər
    start-da yenidən yaradılır.
    """

    def __init__(self) -> None:
        self.app = None

    async def __call__(self, scope, receive, send) -> None:
        if self.app is None:
            raise RuntimeError("MCP tətbiqi hazır deyil - lifespan işə düşməyib")
        await self.app(scope, receive, send)


mcp_proxy = _MCPProxy()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Server qalxanda qovluqlar və DB cədvəlləri hazır olsun
    settings.ensure_dirs()
    init_db()

    # DİQQƏT: mount olunmuş ASGI tətbiqinin öz lifespan-ı AVTOMATİK işə düşmür.
    # MCP-nin sessiya meneceri məhz orada başlayır - onu əl ilə açmasaq,
    # /mcp ünvanı 500 qaytarır və səbəbi heç bir yerdə görünmür.
    mcp_app = mcp_http_app()
    async with mcp_app.router.lifespan_context(mcp_app):
        mcp_proxy.app = mcp_app
        try:
            yield
        finally:
            mcp_proxy.app = None


app = FastAPI(
    title="BasketIQ",
    description="Supermarket kataloqlarından qiymət kəşfiyyatı",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", RevalidatedStaticFiles(directory=STATIC_DIR), name="static")
app.include_router(catalogs.router)
app.include_router(catalog.router)
app.include_router(products.router)
app.include_router(match.router)
app.include_router(basket.router)
app.include_router(scrape.router)
app.include_router(analytics.router)
app.include_router(profile.router)
app.include_router(voice.router)
app.mount("/mcp", mcp_proxy)


@app.get("/", include_in_schema=False)
def dashboard():
    # index.html da eyni səbəbdən keşlənməməlidir: köhnə HTML köhnə
    # element adları ilə gəlsə, yeni CSS ona yapışmır və səhifə sınır.
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": NO_CACHE})


@app.get("/product/{product_id}", include_in_schema=False)
def product_page(product_id: int):
    """
    Məhsul səhifəsi — trolley üslubunda ayrıca ünvan.

    NİYƏ MODAL DEYİL, AYRICA SƏHİFƏ?
    Ünvan paylaşıla bilməlidir: «bu südü Arazdan al» deyəndə linki
    göndərmək lazımdır. Modal-ın ünvanı yoxdur, geri düyməsi də onu
    bağlamır — brauzerin öz naviqasiyası ilə ziddiyyət yaradır.

    `product_id` yolun içindədir, amma HTML statikdir: hansı məhsul
    olduğunu `product.js` ünvandan oxuyub API-dən soruşur. Beləliklə
    server tərəfdə şablon mühərriki lazım gəlmir.
    """
    return FileResponse(STATIC_DIR / "product.html", headers={"Cache-Control": NO_CACHE})


@app.get("/search", include_in_schema=False)
def search_page():
    """
    Axtarış / kateqoriya nəticələri səhifəsi.

    Filtr vəziyyəti ÜNVANDADIR (`?q=...&market=...`), yəni nəticə paylaşıla
    və brauzerin «geri» düyməsi ilə gəzilə bilər. Serverdə şablon yoxdur -
    `search.js` parametrləri ünvandan oxuyub API-ni çağırır.
    """
    return FileResponse(STATIC_DIR / "search.html", headers={"Cache-Control": NO_CACHE})


@app.get("/store/{slug}", include_in_schema=False)
def store_page_html(slug: str):
    """
    Market səhifəsi — ana səhifədəki loqo şəbəkəsindən buraya keçilir.

    `product_page()` ilə eyni yanaşma: HTML statikdir, hansı market olduğunu
    `store.js` ünvandan oxuyur. Slug-ın doğruluğunu API yoxlayır (reyestrdə
    yoxdursa 404) - burada yoxlamaq HTML-i də şablona çevirərdi.
    """
    return FileResponse(STATIC_DIR / "store.html", headers={"Cache-Control": NO_CACHE})


@app.get("/health", response_model=HealthResponse)
def health():
    """DB və Ollama işləyirmi? Deploy sonrası ilk yoxlayacağımız endpoint."""
    llm = check_llm()
    try:
        db = db_stats()
        db_ok = True
    except Exception as e:
        db = {"error": str(e)}
        db_ok = False

    status = "ok" if (db_ok and llm.get("reachable")) else "degraded"
    return HealthResponse(status=status, env=settings.app_env, database=db, llm=llm)
