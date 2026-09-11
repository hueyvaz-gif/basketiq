"""
DEPLOY KONFİQURASİYASI — kiçik droplet üçün iki düzəliş (2026-09-11).

1. CHROME KONTEYNERDƏ YOX İDİ. Mağaza qatının gündəlik qiymətləri
   (`ingestion/shop.py`, Wolt) həmişə headless Chrome ilə çəkilir, Dockerfile
   isə onu quraşdırmırdı: serverdə sayt açılacaqdı, qiymətlər yenilənməyəcəkdi.
2. OLLAMA MƏCBURİ İDİ. `LLM_PROVIDER=claude` ilə o yalnız ehtiyatdır, amma
   compose hər `up`-da ~9 GB-lıq image-i endirib konteyneri qaldırırdı.
"""

import re
from pathlib import Path

import yaml

from app.config import settings

ROOT = Path(__file__).resolve().parent.parent


def _services() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]


# ------------------------------------------------------------------ Ollama


def test_ollama_seçimli_profildədir():
    services = _services()

    assert services["ollama"].get("profiles") == ["ollama"]
    # Asılılıq qalsaydı, profilsiz `up` Ollama-nı yenə qaldırardı.
    assert "ollama" not in (services["basketiq"].get("depends_on") or [])


def test_profilsiz_yalnız_tətbiq_qalxır():
    """n8n də seçimlidir - defolt `up` yalnız BasketIQ-i qaldırmalıdır."""
    profilsiz = [ad for ad, s in _services().items() if not s.get("profiles")]

    assert profilsiz == ["basketiq"]


def test_claude_işləyəndə_ollamanın_yoxluğu_degraded_deyil(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "check_llm", lambda: {"reachable": False, "provider": "claude"})
    monkeypatch.setattr(main, "claude_enabled", lambda: True)
    assert main.health().status == "ok"

    # Claude da yoxdursa - LLM həqiqətən yoxdur, "degraded" doğrudur.
    monkeypatch.setattr(main, "claude_enabled", lambda: False)
    assert main.health().status == "degraded"


# ------------------------------------------------------------------ Chrome


def test_dockerfile_chromium_və_drayverini_quraşdırır():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert re.search(r"^\s+chromium \\$", dockerfile, re.M)
    assert re.search(r"^\s+chromium-driver \\$", dockerfile, re.M)
    # Debian paketlərinin yolları - brauzer köməkçisi bunları oxuyur.
    assert "CHROME_BIN=/usr/bin/chromium" in dockerfile
    assert "CHROMEDRIVER_PATH=/usr/bin/chromedriver" in dockerfile


def test_env_faylı_chromium_yolunu_ezə_bilmir():
    """
    `.env.example`-dakı boş `CHROME_BIN=` `cp .env.example .env` ilə env_file-a,
    oradan konteynerə düşsəydi, Dockerfile-ın ENV-ini EZƏRDİ (compose:
    environment > env_file > image ENV) - brauzer yolu boş qalardı.
    """
    env = _services()["basketiq"]["environment"]

    assert env["CHROME_BIN"] == "/usr/bin/chromium"
    assert env["CHROMEDRIVER_PATH"] == "/usr/bin/chromedriver"
    nümunə = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert not any(s.startswith(("CHROME_BIN=", "CHROMEDRIVER_PATH=")) for s in nümunə)


def test_brauzer_seçimləri_konteyner_üçün_hazırdır(monkeypatch):
    from ingestion.browser import chrome_options

    monkeypatch.setattr(settings, "chrome_binary", "/usr/bin/chromium")
    opts = chrome_options("--window-size=1400,1600")

    for arg in (
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",  # Docker /dev/shm 64 MB - onsuz Chrome çökür
        "--window-size=1400,1600",
        f"--user-agent={settings.user_agent}",
    ):
        assert arg in opts.arguments
    assert opts.binary_location == "/usr/bin/chromium"


def test_lokalda_brauzer_yolu_verilmir(monkeypatch):
    """Boş yol = Selenium Manager lokal Chrome-u özü tapır (indiki davranış)."""
    from ingestion.browser import chrome_options

    monkeypatch.setattr(settings, "chrome_binary", "")

    assert chrome_options().binary_location == ""


def test_drayver_yolu_verilibsə_o_işlədilir(monkeypatch):
    import selenium.webdriver as webdriver

    from ingestion import browser

    tutulan = {}
    monkeypatch.setattr(webdriver, "Chrome", lambda **kw: tutulan.update(kw) or "driver")
    monkeypatch.setattr(settings, "chromedriver_path", "/usr/bin/chromedriver")

    assert browser.new_chrome() == "driver"
    assert tutulan["service"].path == "/usr/bin/chromedriver"


def test_bütün_brauzer_açılışları_bir_yerdən_keçir():
    """Yeni yer köməkçidən yan keçsə, konteynerdə Chromium yolunu bilməyəcək."""
    fayllar = [p for d in ("app", "ingestion", "tools", "mcp_server", "ai") for p in (ROOT / d).rglob("*.py")]

    birbaşa = [p.relative_to(ROOT).as_posix() for p in fayllar if "webdriver.Chrome(" in p.read_text(encoding="utf-8")]

    assert birbaşa == ["ingestion/browser.py"]
