"""
HEADLESS CHROME — layihədəki bütün brauzer açılışları buradan keçir.

Üç yer brauzer açır: mağaza qatı (`ingestion/shop.py`, Wolt — gündəlik
qiymətlər), kataloq ehtiyat yolu (`ingestion/scraper.py`) və mənbə yoxlaması
(`tools/check_source.py`). Əvvəl hər biri seçimləri özü yazırdı; Docker-ə
Chromium əlavə olunanda (2026-09-11) üçünə də eyni iki şey lazım oldu:

  1. BRAUZER VƏ DRAYVER YOLU mühitdən gəlir (`CHROME_BIN`, `CHROMEDRIVER_PATH`).
     Lokalda boşdur — Selenium Manager quraşdırılmış Chrome-u özü tapır.
     Konteynerdə Debian-ın `chromium` + `chromium-driver` paketləridir: yol
     verilməsə, Selenium Manager `chromium`-u Chrome kimi tanımayıb işləmə
     vaxtı internetdən «Chrome for Testing» endirməyə cəhd edərdi.
  2. `--disable-dev-shm-usage`: Docker `/dev/shm`-i 64 MB verir; ağır səhifədə
     (Wolt-un virtual siyahısı) Chrome orada yer tapmayıb ÇÖKÜR. Bayraq onu
     `/tmp`-yə yönəldir. Lokalda zərərsizdir.

LAZY IMPORT: selenium yalnız brauzer lazım olanda yüklənir — Chrome
quraşdırılmayan maşında layihənin qalanı işləyir.
"""

from app.config import settings


def chrome_options(*extra: str):
    """Ümumi headless seçimləri + çağıranın əlavələri (məs. pəncərə ölçüsü)."""
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    for arg in ("--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage", *extra):
        opts.add_argument(arg)
    # Gizlətmə YOXDUR: robots.txt-i hansı adla oxuyuruqsa, səhifəni də həmin
    # adla açırıq.
    opts.add_argument(f"--user-agent={settings.user_agent}")
    if settings.chrome_binary:
        opts.binary_location = settings.chrome_binary
    return opts


def new_chrome(options=None):
    """Chrome-u qaldırır. Drayver yolu verilibsə, Selenium Manager işə düşmür."""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service

    service = Service(executable_path=settings.chromedriver_path) if settings.chromedriver_path else None
    return webdriver.Chrome(options=options or chrome_options(), service=service)
