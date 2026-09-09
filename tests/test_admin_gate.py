"""
ADMİN QAPISI (B11) — panel istehsalda bağlıdır.

NİYƏ TEST LAZIMDIR? Qapının açıq qalması HEÇ BİR ƏLAMƏT VERMİR: sayt işləyir,
səhifə normal görünür, testlər yaşıl keçir. Fərq yalnız o vaxt bilinir ki,
kimsə `/api/catalogs` ünvanına birbaşa müraciət edib kataloq silir.

Testlər iki tərəfi də yoxlayır:
  1. qapı bağlananda ADMİN səthi çatılmaz olur;
  2. qapı bağlananda İSTİFADƏÇİ səthi toxunulmaz qalır - qoruma çox geniş
     qoyulsa, sayt istehsalda ümumiyyətlə işləməzdi.
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

# Admin səthi: hər üç router. Yeni admin router-i əlavə edən bu siyahını da
# genişləndirməlidir - `test_hər_admin_router_i_siyahıdadır` bunu tutur.
ADMIN_YOLLARI = [
    ("GET", "/api/catalogs"),
    ("GET", "/api/review/flagged"),
    ("POST", "/api/review/flagged/1/approve"),
    ("GET", "/api/scrape/sources"),
]

İSTİFADƏÇİ_YOLLARI = [
    "/api/catalog/deals",
    "/api/catalog/markets",
    "/api/analytics/discounts",
    "/api/basket/compare",
    "/health",
]


@pytest.fixture
def qapı_bağlı():
    """Qapını bağlayır və testdən sonra əvvəlki vəziyyəti qaytarır."""
    əvvəlki = settings.admin_enabled
    settings.admin_enabled = False
    yield
    settings.admin_enabled = əvvəlki


@pytest.mark.parametrize("method,path", ADMIN_YOLLARI)
def test_qapı_bağlı_olanda_admin_səthi_404_verir(qapı_bağlı, method, path):
    """
    404, 403 DEYİL. «İcazən yoxdur» cavabı endpoint-in MÖVCUD olduğunu
    təsdiqləyər və axtaran adama xəritə verər.
    """
    assert client.request(method, path).status_code == 404


@pytest.mark.parametrize("path", İSTİFADƏÇİ_YOLLARI)
def test_qapı_bağlı_olanda_istifadəçi_səthi_işləyir(qapı_bağlı, path):
    """Qoruma çox geniş qoyulsa, sayt istehsalda ümumiyyətlə açılmazdı."""
    assert client.get(path).status_code == 200


# Açıq qapıda 200 gözlənilən yollar. Təsdiq (POST .../approve) burada YOXDUR:
# o, mövcud olmayan sətir üçün qapıdan asılı olmayaraq 404 verir - yəni bu
# testdə heç nə sübut etməzdi.
AÇIQ_YOLLAR = [yol for metod, yol in ADMIN_YOLLARI if metod == "GET"]


@pytest.mark.parametrize("path", AÇIQ_YOLLAR)
def test_qapı_açıq_olanda_admin_səthi_çatılandır(path):
    """
    Əks tərəf: qapı həmişə bağlı qalsaydı, yuxarıdakı test yenə keçərdi və
    heç kim fərqi bilməzdi.
    """
    assert client.get(path).status_code == 200


def test_vəziyyət_endpoint_i_qapı_bağlı_olanda_da_cavab_verir(qapı_bağlı):
    """
    `nav.js` tabı bu cavaba görə gizlədir. Endpoint qapının arxasında
    olsaydı, bağlı halda özü də 404 verər və brauzer heç nə öyrənə bilməzdi.
    """
    res = client.get("/api/admin/state")
    assert res.status_code == 200
    assert res.json() == {"enabled": False}


def test_vəziyyət_endpoint_i_həqiqəti_deyir():
    assert client.get("/api/admin/state").json()["enabled"] is settings.admin_enabled


def _routerlər():
    """
    Tətbiqə qoşulmuş BÜTÜN router-lər: (prefiks, router).

    FastAPI qoşulmuş router-i `_IncludedRouter` qabığına salır və orijinalı
    `original_router` sahəsində saxlayır. Qabığın öz `routes` siyahısı yoxdur,
    ona görə birbaşa `app.routes` üzərində gəzmək HEÇ NƏ tapmır - bu test
    əvvəlcə məhz belə yazılmışdı və sükutla boş keçirdi (mutasiya ilə
    yoxlanıldı: qapını silmək testi sındırmırdı).
    """
    üçün = []
    for route in app.routes:
        router = getattr(route, "original_router", None)
        if router is not None:
            üçün.append((getattr(router, "prefix", ""), router))
    return üçün


def test_hər_admin_router_i_qapının_arxasındadır():
    """
    ƏSAS TEST. Yuxarıdakılar SİYAHIDAKI yolları yoxlayır; bu isə tətbiqin
    ÖZÜNDƏN gedir. Yeni admin endpoint-i qapısız əlavə olunsa, yol siyahısına
    da düşməyəcək - yəni heç bir test onu görməyəcəkdi.
    """
    from app.security import require_admin

    ADMİN_PREFİKSLƏRİ = ("/api/catalogs", "/api/scrape", "/api/review")

    yoxlanan = 0
    for prefiks, router in _routerlər():
        if not prefiks.startswith(ADMİN_PREFİKSLƏRİ):
            continue
        yoxlanan += 1
        asılılıqlar = [d.dependency for d in getattr(router, "dependencies", [])]
        assert require_admin in asılılıqlar, f"{prefiks} qapısızdır"

    assert yoxlanan == len(ADMİN_PREFİKSLƏRİ), (
        f"admin router-lərinin hamısı tapılmadı: {yoxlanan}/{len(ADMİN_PREFİKSLƏRİ)}"
    )


def test_istifadəçi_routerləri_qapının_arxasında_deyil():
    """
    Qapı səhvən ümumi router-ə qoyulsa, sayt istehsalda tamamilə bağlanardı -
    və bunu yalnız canlı serverdə görmək olardı.
    """
    from app.security import require_admin

    for prefiks, router in _routerlər():
        if prefiks.startswith(("/api/catalogs", "/api/scrape", "/api/review")):
            continue
        asılılıqlar = [d.dependency for d in getattr(router, "dependencies", [])]
        assert require_admin not in asılılıqlar, f"{prefiks} səhvən qapıya salınıb"


def test_defolt_istehsalda_bağlıdır():
    """
    Qapının DEFOLTU vacibdir: unudulan konfiqurasiya istehsalda AÇIQ panel
    deməkdir. `.env` faylı olmayan serverdə də bağlı olmalıdır.

    AYRI PROSESDƏ yoxlanılır. `importlib.reload(app.config)` ilə cəhd edildi
    və REAL ZƏRƏR VERDİ: reload YENİ `settings` obyekti yaradır, `app/security.py`
    isə köhnəsini saxlayır. Nəticədə sonrakı testlərdə qapı «bağlandı» deyilib
    açıq qalırdı - səhv yalnız tam qaçışda görünürdü, tək testdə yox.
    """
    import subprocess
    import sys

    mühit = {
        **os.environ,
        "APP_ENV": "production",
        "PYTHONIOENCODING": "utf-8",
    }
    mühit.pop("ADMIN_ENABLED", None)

    nəticə = subprocess.run(
        [sys.executable, "-c", "from app.config import settings; print(settings.admin_enabled)"],
        capture_output=True,
        text=True,
        env=mühit,
        cwd=Path(__file__).resolve().parent.parent,
    )
    assert nəticə.returncode == 0, nəticə.stderr
    assert nəticə.stdout.strip() == "False", f"istehsalda panel açıq qalır: {nəticə.stdout!r}"
