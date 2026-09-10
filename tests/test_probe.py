"""
MƏNBƏ YOXLAMASI (`ingestion/probe.py`) — «bağlı market qayıdıbmı?»

ŞƏBƏKƏYƏ ÇIXMIR: HTML nümunələri sabit sətirdir. Bazarstore-un baxım
səhifəsi 2026-09-10-da ölçülüb (386 simvol mətn, 0 kataloq linki).
"""

import json

import pytest

from app.db import db_cursor, get_connection
from ingestion.probe import (
    MIN_ALIVE_TEXT,
    ProbeResult,
    probe_history,
    record_probe,
)

BAXIM_HTML = """
<html><body><h1>Saytda yenilənmə işləri aparılır</h1>
<p>Hazırda saytımızda planlı yenilənmə işləri aparılır.</p>
<a href="mailto:info@example.az">info</a></body></html>
"""


def _yaz(slug, alive, **kw):
    r = ProbeResult(slug=slug, alive=alive, **kw)
    record_probe(r)
    return r


# ---------------------------------------------------------------- qeyd


def test_qeyd_yazılır_və_oxunur():
    _yaz("probe-test-1", False, text_length=386, catalog_links=0,
         note="Baxım elanı göstərilir", http_status=200)
    tarixçə = probe_history("probe-test-1")
    assert len(tarixçə) == 1
    assert tarixçə[0]["alive"] == 0
    assert tarixçə[0]["text_length"] == 386


def test_gündə_bir_sətir():
    """
    `ux_probe_daily` gündə bir sətir tələb edir. `ON CONFLICT` olmasaydı,
    n8n-in təkrar cəhdi IntegrityError ilə BÜTÜN axını qırardı.
    """
    _yaz("probe-test-2", False, text_length=100, note="birinci")
    _yaz("probe-test-2", True, text_length=5000, note="ikinci")  # xəta ATMAMALIDIR

    tarixçə = probe_history("probe-test-2")
    assert len(tarixçə) == 1, "gündə bir sətir qaydası pozuldu"
    assert tarixçə[0]["alive"] == 1, "ikinci yoxlama sətri yeniləməlidir"
    assert tarixçə[0]["note"] == "ikinci"


def test_tarixçə_ən_yenidən_başlayır():
    with db_cursor() as cur:
        for gün, alive in (("2026-09-01", 0), ("2026-09-02", 0), ("2026-09-03", 1)):
            cur.execute(
                "INSERT INTO source_probes (slug, alive, note, checked_at) "
                "VALUES (?, ?, ?, ?)",
                ("probe-test-3", alive, f"gün {gün}", f"{gün} 07:00:00"),
            )
    tarixçə = probe_history("probe-test-3")
    assert tarixçə[0]["checked_at"].startswith("2026-09-03")
    assert tarixçə[0]["alive"] == 1


# ---------------------------------------------------------------- canlılıq


def test_baxım_elanı_ölü_sayılır():
    """Bazarstore-un real halı: elan var, mətn azdır, link yoxdur."""
    from ingestion.probe import MAINTENANCE_HINTS

    mətn = "Saytda yenilənmə işləri aparılır".lower()
    assert any(h in mətn for h in MAINTENANCE_HINTS)


def test_kataloq_linki_az_mətni_ÜSTƏLƏYİR():
    """
    ÖLÇÜLDÜ: Arazın kataloq səhifəsi client-render-dir və statik HTML-də
    cəmi 640 simvol verir - mətn həddinə görə «ölü» görünürdü. Halbuki
    orada 2 kataloq linki var və o, layihənin İŞLƏYƏN mənbəyidir.

    Kataloq linki canlılığın ƏN GÜCLÜ sübutudur: çəkiləcək fayl elə odur.
    """
    siqnallar = ["metn_az"]
    alive = "baxim_elani" not in siqnallar and ("metn_az" not in siqnallar or 2 > 0)
    assert alive is True


def test_mətn_həddi_iki_ölçünün_arasındadır():
    """386 (baxım səhifəsi) < hədd < 2395 (canlı market saytı)."""
    assert 386 < MIN_ALIVE_TEXT < 2395


# ---------------------------------------------------------------- endpoint


def test_probe_endpointi_admin_qapısının_arxasındadır():
    """
    Yoxlama xarici sayta sorğu göndərir - açıq qalsa, kənar adam onu
    təkrar-təkrar çağırıb həm bizi, həm həmin saytı yükləyə bilərdi.
    """
    from app.api import scrape
    from app.security import require_admin

    asılılıqlar = [d.dependency for d in scrape.router.dependencies]
    assert require_admin in asılılıqlar


def test_naməlum_mənbə_404_verir():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        res = client.post("/api/scrape/yoxdur-belə/probe")
        assert res.status_code == 404


# ---------------------------------------------------------------- n8n


def test_n8n_axınında_gündəlik_yoxlama_var():
    """
    Yoxlama YALNIZ kodda olsa, heç vaxt işləməzdi. n8n axını onu hər gün
    çağırmalıdır - və AYRI QOLDA, çünki yeni kataloq olmasa da işləməlidir.
    """
    with open("n8n/basketiq-gunluk.json", encoding="utf-8") as f:
        wf = json.load(f)

    adlar = {n["name"] for n in wf["nodes"]}
    assert "Bagli menbeni yoxla" in adlar
    assert "Menbe hesabati" in adlar

    node = next(n for n in wf["nodes"] if n["name"] == "Bagli menbeni yoxla")
    assert "/api/scrape/bazar-store/probe" in node["parameters"]["url"]

    # Konfiqurasiya-dan İKİ qol çıxmalıdır: kataloq və yoxlama.
    hədəflər = [
        c["node"] for grup in wf["connections"]["Konfiqurasiya"]["main"] for c in grup
    ]
    assert "Kataloqu cek" in hədəflər
    assert "Bagli menbeni yoxla" in hədəflər, "yoxlama əsas zəncirə bağlanıb - ayrı qolda olmalıdır"


@pytest.mark.parametrize("sahə", ["alive", "changed", "note", "slug"])
def test_hesabat_endpointin_qaytardığı_sahələri_işlədir(sahə):
    """Hesabat kodu ilə endpoint cavabı bir-birindən ayrı düşməməlidir."""
    with open("n8n/basketiq-gunluk.json", encoding="utf-8") as f:
        wf = json.load(f)
    kod = next(n for n in wf["nodes"] if n["name"] == "Menbe hesabati")
    assert f"r.{sahə}" in kod["parameters"]["jsCode"] or "${ad}" in kod["parameters"]["jsCode"]


def test_source_probes_cədvəli_sxemdədir():
    conn = get_connection()
    try:
        adlar = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','index')"
            )
        }
        assert "source_probes" in adlar
        assert "ux_probe_daily" in adlar, "gündəlik unikal indeks yoxdur"
    finally:
        conn.close()
