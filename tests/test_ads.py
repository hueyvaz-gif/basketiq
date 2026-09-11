"""
REKLAM SİSTEMİ (E19-E24).

BU BÖLMƏDƏ SƏHVİN QİYMƏTİ ADİDƏN BAHADIR, çünki iki tərəfə birdən dəyir:

  - İSTİFADƏÇİYƏ: reklam endirim kimi görünsə, sayt öz yeganə vədini -
    «qiymətlər yoxlanılıb» - pozur;
  - REKLAMVERƏNƏ: müddəti bitmiş sifariş göstərilsə və ya klik sayılmasa,
    hesabat yalan olur.

Ona görə testlərin yarısı VAXT şərtinə, yarısı isə sayğaclara baxır.
"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.ads import (
    SLOTS,
    create_ad,
    current_ad,
    delete_ad,
    list_ads,
    record_click,
    record_impression,
    rendered_slots,
    seed_sample_ad,
    update_ad,
)
from app.config import settings
from app.db import db_cursor
from app.main import app

client = TestClient(app)

BUGÜN = date.today()
DÜNƏN = (BUGÜN - timedelta(days=1)).isoformat()
SABAH = (BUGÜN + timedelta(days=1)).isoformat()
KEÇƏN_HƏFTƏ = (BUGÜN - timedelta(days=7)).isoformat()
GƏLƏN_HƏFTƏ = (BUGÜN + timedelta(days=7)).isoformat()


@pytest.fixture(autouse=True)
def təmiz_lövhə():
    """Hər test öz sifarişləri ilə işləyir - başqasının qalığı nəticəni pozmasın."""
    with db_cursor() as cur:
        cur.execute("DELETE FROM ads")
    yield
    with db_cursor() as cur:
        cur.execute("DELETE FROM ads")


def _sifariş(**fərq) -> int:
    sahələr = {
        "advertiser": "Test Reklamverən",
        "title": f"Sifariş {uuid.uuid4().hex[:6]}",
        "target_url": "https://example.com/kampaniya",
        "slot": "home-banner",
        "starts_at": DÜNƏN,
        "ends_at": SABAH,
    }
    sahələr.update(fərq)
    return create_ad(**sahələr)


# ------------------------------------------------------- vaxt və vəziyyət


def test_aktiv_və_vaxtında_olan_reklam_göstərilir():
    _sifariş()
    assert current_ad("home-banner") is not None


def test_müddəti_bitmiş_reklam_göstərilmir():
    """
    ƏSAS QAYDA (E21). Admin söndürməyi unutsa belə, ödənilməyən günlərdə
    reklam ekranda qalmamalıdır - bu, reklamverənə verilən sözün texniki
    təminatıdır.
    """
    _sifariş(starts_at=KEÇƏN_HƏFTƏ, ends_at=DÜNƏN)
    assert current_ad("home-banner") is None


def test_hələ_başlamamış_reklam_göstərilmir():
    _sifariş(starts_at=SABAH, ends_at=GƏLƏN_HƏFTƏ)
    assert current_ad("home-banner") is None


def test_söndürülmüş_reklam_göstərilmir():
    _sifariş(active=False)
    assert current_ad("home-banner") is None


def test_vaxt_şərti_ilə_aktivlik_şərti_AYRI_AYRI_işləyir():
    """
    İki şərt VƏ ilə birləşir. Biri unudulsaydı, ya söndürülmüş reklam
    görünərdi, ya müddəti bitmiş - hər ikisi səssiz səhvdir.
    """
    _sifariş(active=False, starts_at=DÜNƏN, ends_at=SABAH)   # yalnız vaxt uyğun
    _sifariş(active=True, starts_at=KEÇƏN_HƏFTƏ, ends_at=DÜNƏN)  # yalnız aktivlik uyğun
    assert current_ad("home-banner") is None


def test_bir_neçə_uyğun_sifarişdən_ən_yenisi_seçilir():
    """Admin yeni sifariş yazanda onun dərhal işə düşməsini gözləyir."""
    _sifariş(title="köhnə")
    yeni = _sifariş(title="yeni")
    assert current_ad("home-banner")["id"] == yeni


def test_naməlum_slot_reklam_qaytarmır():
    """
    Slot adları KODDA sabitdir. Bazadan gələn sərbəst mətn səhifədə yeni yer
    aça bilməz - əks halda səhv yazılmış slot reklamı gözlənilməz yerdə
    göstərərdi.
    """
    with pytest.raises(ValueError):
        _sifariş(slot="uydurma-yer")
    assert current_ad("uydurma-yer") is None


def test_bitmə_tarixi_başlanğıcdan_əvvəl_ola_bilməz():
    with pytest.raises(ValueError):
        _sifariş(starts_at=SABAH, ends_at=DÜNƏN)


# ----------------------------------------------------------------- sayğaclar


def test_göstərim_endpoint_də_sayılır():
    """Hesabat rəqəmi serverdə artır: JS sönük olsa da hesabat işləyir."""
    ad_id = _sifariş()
    client.get("/api/ads/slot/home-banner")
    client.get("/api/ads/slot/home-banner")
    sifarişlər = {a["id"]: a for a in list_ads()}
    assert sifarişlər[ad_id]["impressions"] == 2


def test_boş_slot_göstərim_saymır():
    """Sayılacaq reklam yoxdursa, rəqəm də yaranmamalıdır."""
    client.get("/api/ads/slot/home-banner")
    assert list_ads() == []


def test_klik_sayılır_və_yönləndirir():
    ad_id = _sifariş(target_url="https://example.com/hedef")
    res = client.get(f"/api/ads/{ad_id}/click", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "https://example.com/hedef"
    assert {a["id"]: a for a in list_ads()}[ad_id]["clicks"] == 1


def test_veb_olmayan_hədəf_yönləndirilmir():
    """
    `javascript:` sxemi bazaya düşsəydi, klik keçidi skript icrasına
    çevrilərdi. Sayğac artır (klik həqiqətən baş verib), yönləndirmə isə yox.
    """
    ad_id = _sifariş(target_url="javascript:alert(1)")
    assert client.get(f"/api/ads/{ad_id}/click", follow_redirects=False).status_code == 400


def test_olmayan_reklama_klik_404_verir():
    assert client.get("/api/ads/999999/click", follow_redirects=False).status_code == 404


def test_sayğaclar_əl_ilə_redaktə_oluna_bilmir():
    """
    Hesabat rəqəmini admin panelindən dəyişmək mümkün olsaydı, hesabatın
    özü mənasız olardı - rəqəm ölçmə deyil, iddia olardı.
    """
    ad_id = _sifariş()
    with pytest.raises(ValueError):
        update_ad(ad_id, impressions=1000)
    with pytest.raises(ValueError):
        update_ad(ad_id, clicks=1000)


# --------------------------------------------------------------- admin səthi


def test_admin_səthi_qapının_arxasındadır():
    """Sifariş yaratmaq saytın inventarını dəyişir - ictimai ola bilməz."""
    əvvəlki = settings.admin_enabled
    settings.admin_enabled = False
    try:
        assert client.get("/api/admin/ads").status_code == 404
        assert client.post("/api/admin/ads", json={}).status_code == 404
    finally:
        settings.admin_enabled = əvvəlki


def test_ictimai_slot_qapıdan_asılı_deyil():
    """
    Reklam admin bağlı olanda da göstərilməlidir - əks halda istehsalda
    (`ADMIN_ENABLED=0`) bütün reklamlar yox olardı.
    """
    _sifariş()
    əvvəlki = settings.admin_enabled
    settings.admin_enabled = False
    try:
        res = client.get("/api/ads/slot/home-banner")
        assert res.status_code == 200 and res.json()["ad"] is not None
    finally:
        settings.admin_enabled = əvvəlki


def test_sifariş_endpoint_ilə_yaradılır_və_silinir():
    # Yer SƏHİFƏDƏ OLAN slotdur: görünməyən slota yazmaq artıq 400 verir
    # (bax `test_görünməyən_yerə_sifariş_yazılmır`).
    res = client.post(
        "/api/admin/ads",
        json={
            "advertiser": "Endpoint Reklamverən",
            "title": "Endpoint sifarişi",
            "target_url": "https://example.com",
            "slot": "home-rail-left",
            "starts_at": DÜNƏN,
            "ends_at": SABAH,
        },
    )
    assert res.status_code == 200
    ad_id = res.json()["id"]
    assert current_ad("home-rail-left")["id"] == ad_id

    assert client.delete(f"/api/admin/ads/{ad_id}").status_code == 200
    assert current_ad("home-rail-left") is None


def test_dayandırma_reklamı_ekrandan_çıxarır():
    ad_id = _sifariş()
    client.patch(f"/api/admin/ads/{ad_id}", json={"active": False})
    assert current_ad("home-banner") is None

    client.patch(f"/api/admin/ads/{ad_id}", json={"active": True})
    assert current_ad("home-banner") is not None


def test_naməlum_slota_redaktə_qəbul_edilmir():
    ad_id = _sifariş()
    assert client.patch(f"/api/admin/ads/{ad_id}", json={"slot": "uydurma"}).status_code == 400


def test_olmayan_sifarişin_silinməsi_404_verir():
    assert client.delete("/api/admin/ads/999999").status_code == 404
    assert delete_ad(999999) is False


def test_forma_yalnız_səhifədə_olan_yerləri_təklif_edir():
    """
    Admin forması slot siyahısını KODDAN alır, HTML-də sabit saxlamır - və
    yalnız hansısa səhifədə HƏQİQƏTƏN çəkilən slotları.

    REAL TƏLƏ (2026-09-11): `home-banner` səhifədən götürülmüşdü, forma isə
    onu təklif etməyə davam edirdi. Yaradılan reklam aktiv və vaxtında idi,
    amma heç yerdə görünmədi (göstərim 0).
    """
    slots = {s["key"] for s in client.get("/api/admin/ads").json()["slots"]}
    assert slots == rendered_slots()
    assert "home-banner" not in slots


# -------------------------------------------------- səhifədə olmayan slot


def test_render_olunan_slotlar_html_dən_oxunur():
    """
    Həqiqət HTML-dədir (`data-slot`), ikinci əl siyahısında yox: problem
    məhz köhnələn siyahıdan yarandı. Yan lövhələr ana səhifədədir, sətir
    arası banner isə `bd01e6e`-dən bəri heç bir səhifədə yoxdur.
    """
    assert rendered_slots() == {"home-rail-left", "home-rail-right"}
    assert "home-banner" in SLOTS, "reyestrdə qalır - köhnə sifarişlər itməsin"


def test_görünməyən_yerə_sifariş_yazılmır():
    """Forma onu təklif etmir; API də rədd edir - əl ilə sorğu da görünməz reklam yaratmasın."""
    res = client.post(
        "/api/admin/ads",
        json={
            "advertiser": "X", "title": "Y", "target_url": "https://example.com",
            "slot": "home-banner", "starts_at": DÜNƏN, "ends_at": SABAH,
        },
    )
    assert res.status_code == 400
    assert "göstərilmir" in res.json()["detail"]
    assert list_ads() == []


def test_görünməyən_yerə_köçürmək_olmur_amma_köhnə_sifariş_idarə_olunur():
    """
    Slotu görünməyən yerə DƏYİŞMƏK qadağandır. Amma o yerdə artıq duran köhnə
    sifarişi dayandırmaq, tarixini dəyişmək və ya görünən yerə köçürmək
    mümkün olmalıdır - əks halda o, admin panelində ilişib qalardı.
    """
    lövhə = _sifariş(slot="home-rail-left")
    assert client.patch(f"/api/admin/ads/{lövhə}", json={"slot": "home-banner"}).status_code == 400

    köhnə = _sifariş(slot="home-banner")
    assert client.patch(f"/api/admin/ads/{köhnə}", json={"active": False}).status_code == 200
    assert client.patch(f"/api/admin/ads/{köhnə}", json={"slot": "home-rail-right"}).status_code == 200
    assert {a["id"]: a for a in list_ads()}[köhnə]["slot"] == "home-rail-right"


def test_admin_siyahısı_görünməyən_sifarişi_nişanlayır():
    """«Niyə görünmür?» sualının cavabı admin cədvəlində yazılmalıdır."""
    görünməz = _sifariş(slot="home-banner")
    görünən = _sifariş(slot="home-rail-left")
    items = {a["id"]: a for a in client.get("/api/admin/ads").json()["items"]}
    assert items[görünməz]["on_page"] is False
    assert items[görünən]["on_page"] is True


def test_admin_cədvəli_görünməyən_sifarişi_efirdə_yazmır():
    """
    Əvvəl belə sifariş «efirdə» nişanı alırdı: admin görünməyən reklamı canlı
    sanırdı. İndi `on_page` həm «canlı» şərtinə, həm də nişana daxildir.
    """
    from pathlib import Path

    js = Path("app/static/ads-admin.js").read_text(encoding="utf-8")
    assert 'ad.on_page !== false' in js
    assert 't("adsAdmin.offPage")' in js


# ------------------------------------------------------------ nümunə sifariş


def test_nümunə_sifariş_boş_bazada_yaranır():
    """E24: slot canlı nümunə ilə gəlir ki, yer boş görünməsin."""
    assert seed_sample_ad() is not None
    ad = current_ad("home-banner")
    assert ad["advertiser"] == "Araz Market"
    assert ad["is_sample"] is True


def test_nümunə_sifariş_təkrar_yaranmır():
    """
    İdempotentlik: admin nümunəni silsə, o, növbəti başlanğıcda geri
    qayıtmamalıdır - əks halda silmək mümkünsüz görünərdi.

    SAY ÜÇDÜR (banner + iki yan lövhə): hər satıla bilən yer üçün bir
    nümunə. Boş lövhə «xarab görünür», dolu lövhə isə inventarın necə
    göründüyünü həm satıcıya, həm istifadəçiyə göstərir.
    """
    seed_sample_ad()
    assert seed_sample_ad() is None, "təkrar çağırış yeni sifariş yaratmamalıdır"

    reklamlar = list_ads()
    assert len(reklamlar) == len(SLOTS), "hər slot üçün bir nümunə olmalıdır"
    assert {a["slot"] for a in reklamlar} == set(SLOTS)
    assert all(a["is_sample"] for a in reklamlar)


def test_nümunə_real_sifarişdən_ayrılır():
    """
    Nişan olmasaydı, hesabatda nümunə ödənişli müştəri kimi sayılardı və
    «reklamımız neçə klik aldı?» sualının cavabı yanlış çıxardı.
    """
    seed_sample_ad()
    real = _sifariş()
    sifarişlər = {a["id"]: a for a in list_ads()}
    assert sifarişlər[real]["is_sample"] is False
    assert any(a["is_sample"] for a in sifarişlər.values())


def test_sayğac_funksiyaları_olmayan_sifarişə_toxunmur():
    record_impression(999999)      # xəta atmamalıdır
    assert record_click(999999) is None


# ---------------------------------------------------------------- yan lövhələr


def test_yan_lovheler_slot_kimi_qeydiyyatdadir():
    """
    Slot adı `SLOTS`-da olmasa, `current_ad()` onu rədd edir və lövhə
    həmişə boş qalardı - səhv səssiz olardı, çünki səhifə yenə açılır.
    """
    assert "home-rail-left" in SLOTS
    assert "home-rail-right" in SLOTS


def test_html_de_yan_lovheler_var():
    from pathlib import Path

    html = Path("app/static/index.html").read_text(encoding="utf-8")
    assert 'data-slot="home-rail-left"' in html
    assert 'data-slot="home-rail-right"' in html
    assert 'class="ad-rail ad-rail-left"' in html


def test_ads_js_butun_slotlari_doldurur():
    """
    Əvvəl yalnız `#adSlot` doldurulurdu. Yan lövhələr üçün ikinci nüsxə
    yazsaydıq, biri dəyişəndə digəri köhnə qalardı.
    """
    from pathlib import Path

    js = Path("app/static/ads.js").read_text(encoding="utf-8")
    assert 'querySelectorAll("[data-slot]")' in js
    assert "getElementById(\"adSlot\")" not in js, "köhnə tək-slot yolu qalıb"


def test_dar_ekranda_lovhe_gizlenir():
    """
    Yer çatmayanda seçim ikidir: məzmunu sıxmaq və ya reklamı gizlətmək.
    Sıxmaq qiymət cədvəlini oxunmaz edir - müqayisə saytında bu, reklam
    gəlirindən bahalı olardı.
    """
    from pathlib import Path

    css = Path("app/static/style.css").read_text(encoding="utf-8")
    assert ".ad-rail { display: none; }" in css
    assert "max-width: 1439px" in css


def test_yan_lovhenin_sekli_hedd_ile_kicilmir():
    """
    REQRESİYA: baza `.ad-image` qaydasında `max-height: 110px` var (sətir
    arası bannerin qutusuna görə). Şaquli lövhədə həmin hədd 160x600
    kreativi ~40px-lik nazik zolağa çevirirdi - brauzerdə görüldü.
    """
    from pathlib import Path

    css = Path("app/static/style.css").read_text(encoding="utf-8")
    rail = css.split(".ad-rail .ad-image")[1].split("}")[0]
    assert "max-height: none" in rail


def test_numune_kreativ_ozunu_gizletmir():
    """Nümunə kreativ real sifariş kimi görünməməlidir."""
    from pathlib import Path

    svg = Path("app/static/images/ads/sample-rail.svg").read_text(encoding="utf-8")
    assert "NÜMUNƏ" in svg
    assert "160 × 600" in svg or "160x600" in svg.replace(" ", "")
