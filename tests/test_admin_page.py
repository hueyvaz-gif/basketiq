"""
ADMİN SƏHİFƏSİNİN AYRILMASI (P6).

ƏVVƏL admin paneli ana səhifənin ikinci tabı idi: alış-veriş edən adam üst
paneldə «Admin / Developer» yazısını görür və bir kliklə scraping, OCR rejimi,
model diaqnostikası ilə qarşılaşırdı. Bunlar məhsulun İÇİdir - cavabı deyil.

BU TESTLƏRİN TUTDUĞU SƏHV GERİ QAYIDA BİLƏR VƏ SƏSSİZ OLAR: kimsə admin
işarələməsini yenidən `index.html`-ə əlavə edər (məsələn rahatlıq üçün) və
heç nə sınmaz - sadəcə istifadəçi yenidən görməli olmadığı şeyi görər.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)
STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


@pytest.fixture
def qapı_bağlı():
    əvvəlki = settings.admin_enabled
    settings.admin_enabled = False
    yield
    settings.admin_enabled = əvvəlki


# ------------------------------------------------------------------ ünvan


def test_admin_səhifəsi_ayrıca_ünvandadır():
    res = client.get("/admin")
    assert res.status_code == 200
    assert "admin.js" in res.text


def test_admin_səhifəsi_qapının_arxasındadır(qapı_bağlı):
    """
    İstehsalda səhifə gizli DEYİL, MÖVCUD deyil. 404 «icazən yoxdur»-dan
    üstündür: 403 səhifənin varlığını təsdiqləyər və axtarana xəritə verər.
    """
    assert client.get("/admin").status_code == 404


# ------------------------------------------------- istifadəçi interfeysi


def test_istifadəçi_səhifəsində_admin_izi_yoxdur():
    """
    Ana səhifə admin panelinin nə işarələməsini, nə də keçidini daşımalıdır.
    Tab qalsaydı, «gizlətmək» yalnız CSS-də olardı - yəni HTML-ə baxan
    istifadəçi onsuz da hər şeyi görərdi.
    """
    html = read("index.html")
    assert "panel-admin" not in html, "admin işarələməsi ana səhifədə qalıb"
    assert 'data-panel="admin"' not in html, "admin tabı ana səhifədə qalıb"
    assert 'href="/admin"' not in html, "ana səhifə admin ünvanına keçid verir"

    canlı = client.get("/").text
    assert "panel-admin" not in canlı


def test_admin_skriptləri_istifadəçiyə_göndərilmir():
    """
    Kataloq yükləmə, scraping, karantin və reklam meneceri kodu adi
    ziyarətçiyə ümumiyyətlə çatmamalıdır - o, bu kodu heç vaxt işlətmir.
    """
    html = read("index.html")
    for skript in ("admin.js", "scrape.js", "review.js", "coverage.js", "ads-admin.js"):
        assert skript not in html, f"{skript} istifadəçi səhifəsinə qoşulub"


def test_admin_səhifəsi_öz_skriptlərini_yükləyir():
    html = read("admin.html")
    for skript in ("admin.js", "scrape.js", "review.js", "coverage.js", "ads-admin.js"):
        assert skript in html, f"admin səhifəsində {skript} yoxdur"


def test_istifadəçi_kodu_admin_elementlərindən_asılı_deyil():
    """
    ƏSAS RİSK. `app.js` yükləndiyi anda elementləri axtarır: admin
    işarələməsi səhifədən çıxanda həmin sətirlər `null`-a düşüb BÜTÜN faylı
    qırardı - yəni istifadəçi səhifəsi admin markup-ından asılı olardı.
    Ona görə admin məntiqi ayrı fayla (`admin.js`) köçürüldü.
    """
    app_js = read("app.js")
    for element in ("#dropzone", "#uploadBtn", "#extractBtn", "#matchBtn", "#catalogList"):
        assert element not in app_js, f"app.js hələ də {element} elementini axtarır"


def test_admin_kodu_istifadəçi_elementlərini_axtarmır():
    """Əks tərəf: admin səhifəsində səbət və müqayisə cədvəli yoxdur."""
    admin_js = read("admin.js")
    for element in ("#compareTableWrap", "#basketList", "#storeBars", "#searchInput"):
        assert element not in admin_js, f"admin.js hələ də {element} elementini axtarır"
