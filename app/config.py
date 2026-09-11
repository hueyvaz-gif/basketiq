"""
Bütün konfiqurasiya bir yerdə toplanır.

Niyə belə? Kodun heç bir yerində os.getenv() axtarmamaq üçün. Bir dəyişənin
adını dəyişsən, yalnız bu fayla toxunursan. Açarlar heç vaxt kodda yazılmır.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Layihənin kök qovluğu (bu fayl app/ içindədir, ona görə iki dəfə yuxarı)
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _path(name: str, default: Path) -> Path:
    """
    Yol dəyişəni: mütləq yol olduğu kimi, nisbi yol isə layihə kökünə görə.

    Niyə lazımdır? Konteynerdə data image-in içində qalmamalıdır - restart
    zamanı itərdi. `DATA_DIR=/data` verib bütün yazılan faylları qalıcı
    volume-a köçürürük, kodda isə heç nə dəyişmir.
    """
    raw = _str(name)
    if not raw:
        return default
    path = Path(raw)
    return path if path.is_absolute() else BASE_DIR / path


def _bool(name: str, default: bool) -> bool:
    """
    Bayraq dəyişəni. BOŞ DƏYƏR = VERİLMƏYİB -> defolt (`_path` və `_int` kimi).

    Əvvəl `ADS_COUNT=` (boş) `False` oxunurdu: istehsalda `.env`-də boş sətir
    reklam sayğacını SƏSSİZCƏ söndürərdi və `.env.example`-dakı «boş buraxılsa,
    APP_ENV-dən hesablanır» şərhi yalan olardı (2026-09-11, testdə tutuldu).
    """
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# Modul səviyyəsində hesablanır, çünki sinif gövdəsindən funksiya çağırmaq olmaz
DATA_DIR = _path("DATA_DIR", BASE_DIR / "data")

# YÜKLƏNƏN VƏ YARADILAN ŞƏKİLLƏR: reklam kreativi, məhsul fotosu, kataloq kəsiyi.
#
# Lokalda defolt `app/static`-dir - fayllar kodun yanındadır, heç nə dəyişmir.
# Docker-də `MEDIA_DIR=/data/media` verilir: şəkillər bazanın yanında, EYNİ
# volume-dadır. Əvvəl onlar həmişə `app/static`-də idi - konteynerdə bu, image-in
# öz fayl sistemidir və hər yeniləmədə (`build` + `up`) silinirdi, baza isə
# hələ də onlara istinad edirdi (2026-09-11-də, ilk deploy-dan əvvəl tapıldı).
# URL-lər DƏYİŞMİR: `/static` mount-u əvvəl koda, sonra buraya baxır (app/main.py).
MEDIA_DIR = _path("MEDIA_DIR", BASE_DIR / "app" / "static")


class Settings:
    # --- LLM ---
    # Hansı model əsasdır? "ollama" (defolt) və ya "claude".
    # "claude" seçilsə Claude API əsas, Ollama isə EHTİYAT olur - biri qırılsa
    # digəri işə düşür (bax: ai/llm.py).
    llm_provider: str = _str("LLM_PROVIDER", "ollama").lower()
    # ANTHROPIC_API_KEY - SDK-nın öz standart adıdır, dəyişmirik.
    anthropic_api_key: str = _str("ANTHROPIC_API_KEY", "")
    # DİQQƏT: qalan adlar LLM_ ilə başlayır, CLAUDE_ ilə YOX.
    # Səbəb real problemdir: Claude Code mühitində `CLAUDE_EFFORT` artıq
    # təyin olunub və bizim ayarımızı SÜKUTLA əvəz edirdi (low -> high).
    # Ümumi adlar başqa alətlərlə toqquşur; layihənin öz prefiksi qorunmalıdır.
    llm_claude_model: str = _str("LLM_CLAUDE_MODEL", "claude-opus-5")
    # Düşünmə dərinliyi: low | medium | high | xhigh | max.
    # Bu layihədə çıxarış qısa JSON qaytarır - "low" kifayətdir və ucuzdur.
    llm_claude_effort: str = _str("LLM_CLAUDE_EFFORT", "low")
    llm_claude_timeout: int = _int("LLM_CLAUDE_TIMEOUT_SECONDS", 60)
    # Claude üçün AYRICA limit - Ollama-nın LLM_NUM_PREDICT-i burada işləmir.
    # Səbəb: Claude-un "düşünmə" (thinking) tokenləri də max_tokens-ə daxildir.
    # 800 verilsə, model düşünməyə xərcləyib JSON-u yarımçıq kəsə bilər;
    # yarımçıq JSON isə parser-i sındırır və bu, fallback-lə xilas OLUNMUR.
    # Xərcə təsiri yoxdur: yalnız TAVANdır, real işlənmiş token qədər ödəyirik.
    llm_claude_max_tokens: int = _int("LLM_CLAUDE_MAX_TOKENS", 4000)

    ollama_base_url: str = _str("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = _str("OLLAMA_MODEL", "qwen3:8b")
    llm_temperature: float = _float("LLM_TEMPERATURE", 0.0)
    llm_max_concurrency: int = _int("LLM_MAX_CONCURRENCY", 2)
    llm_timeout_seconds: int = _int("LLM_TIMEOUT_SECONDS", 180)
    llm_keep_alive: str = _str("LLM_KEEP_ALIVE", "60s")   # bundan sonra model RAM-dan boşalır
    llm_num_thread: int = _int("LLM_NUM_THREAD", 3)       # 4 nüvədən 1-i sistemə qalsın
    llm_num_predict: int = _int("LLM_NUM_PREDICT", 800)   # cavabın maksimum uzunluğu
    # Kontekst pəncərəsi. Qwen3 262144-ə qədər dəstəkləyir, amma bizim prompt ~300 tokendir.
    # Kiçik dəyər -> az RAM, sürətli emal.
    llm_num_ctx: int = _int("LLM_NUM_CTX", 1024)

    # --- App ---
    app_env: str = _str("APP_ENV", "development")
    app_host: str = _str("APP_HOST", "127.0.0.1")
    app_port: int = _int("APP_PORT", 8000)
    ingest_api_key: str = _str("INGEST_API_KEY", "dev-secret-change-me")

    # ADMİN PANELİ (B11) — istehsalda BAĞLIDIR.
    #
    # Panel kataloq yükləyir, mənbədən çəkir, kataloq silir və karantin
    # qərarı verir. Bunlar saytın datasını dəyişən əməliyyatlardır; ictimai
    # keçid arxasında qalması o deməkdir ki, ünvanı bilən hər kəs onları
    # işlədə bilər. Layihədə istifadəçi hesabı yoxdur, ona görə qapı ən
    # sadə formadadır: mühit dəyişəni.
    #
    # DEFOLT MÜHİTDƏN ASILIDIR: developmentdə açıq (yerli iş dayanmasın),
    # productionda bağlı. `ADMIN_ENABLED=1` istehsalda da açır - bu, ŞÜURLU
    # qərar tələb edir.
    admin_enabled: bool = _bool("ADMIN_ENABLED", _str("APP_ENV", "development") != "production")

    # REKLAM SAYĞACI (göstərim/klik) — YALNIZ İSTEHSALDA SAYILIR (2026-09-11).
    #
    # Lokalda sayt sahibinin öz baxışları real reklamverənin hesabatına
    # yazılırdı: bir gündə LTC LAB-a 15 «göstərim» düşdü - hamısı səhifəni
    # yeniləyən tərtibatçı idi (server jurnalı: hər `GET /`-dan sonra bir slot
    # sorğusu), sayğac isə dəfələrlə əl ilə sıfırlanırdı. Defolt admin_enabled
    # kimi mühitdən asılıdır; `ADS_COUNT=1` lokalda da sayır (sayğacı sınamaq üçün).
    ads_count_enabled: bool = _bool("ADS_COUNT", _str("APP_ENV", "development") == "production")

    # REKLAM ƏLAQƏ ÜNVANI (E20). Boş slotdakı «Reklam ver» düyməsi buraya
    # yazır. UYDURMA ÜNVAN YAZILMIR: qeyri-mövcud e-poçt reklamverəni
    # itirilmiş məktubla qoyar. Boş qalsa, UI düyməni ümumiyyətlə göstərmir,
    # yalnız «bu yer satılır» yazısı qalır.
    ads_contact: str = _str("ADS_CONTACT", "")

    # --- MƏHSUL ŞƏKİLLƏRİ (M3) ---
    #
    # ETİBAR EŞİYİ KONFİQDƏDİR, çünki onu datanın üzərində kalibrləmək lazım
    # gəlir: eşik aşağı olsa səhv şəkil düşür, yüksək olsa əhatə itir.
    # «Səhv şəkildənsə ikon yaxşıdır» prinsipi ilə defolt YÜKSƏKDİR.
    product_image_min_confidence: float = _float("PRODUCT_IMAGE_MIN_CONFIDENCE", 0.75)

    # İki namizədin balı bu qədər yaxındırsa, İKİSİ DƏ şübhəlidir: seçim
    # təsadüfə çevrilir. Belə hal rədd olunur və manual siyahıya yazılır.
    product_image_ambiguity_gap: float = _float("PRODUCT_IMAGE_AMBIGUITY_GAP", 0.05)

    # Nəzakət: saniyədə bir sorğudan çox getmir (3.3).
    product_image_delay_seconds: float = _float("PRODUCT_IMAGE_DELAY_SECONDS", 1.0)
    product_image_timeout: int = _int("PRODUCT_IMAGE_TIMEOUT", 10)
    product_image_max_bytes: int = _int("PRODUCT_IMAGE_MAX_BYTES", 5 * 1024 * 1024)
    product_image_max_side: int = _int("PRODUCT_IMAGE_MAX_SIDE", 600)

    # --- Yollar ---
    # Yazılan hər şey DATA_DIR altındadır: baza, xam kataloqlar, OCR mətni, keş.
    # Deployment-də bu, tək volume kimi bağlanır (bax: deploy/README.md).
    base_dir: Path = BASE_DIR
    data_dir: Path = DATA_DIR
    raw_dir: Path = DATA_DIR / "raw"      # yüklənmiş PDF/JPG kataloqlar
    text_dir: Path = DATA_DIR / "text"    # OCR/pypdf çıxışı
    db_path: Path = _path("DATABASE_PATH", DATA_DIR / "basketiq.db")
    media_dir: Path = MEDIA_DIR           # şəkillər (yuxarıdakı MEDIA_DIR qeydinə bax)

    # --- OCR ---
    tesseract_cmd: str = _str("TESSERACT_CMD", "")
    tesseract_langs: str = _str("TESSERACT_LANGS", "aze+eng+rus")
    # Dil faylları layihə daxilində saxlanılır -> "Program Files"-a admin hüququ lazım deyil
    tessdata_dir: Path = BASE_DIR / _str("TESSDATA_DIR", "data/tessdata")
    ocr_psm: int = _int("OCR_PSM", 6)             # Tesseract səhifə seqmentasiya rejimi
    ocr_scale: float = _float("OCR_SCALE", 2.0)   # skan səhifəni neçə dəfə böyüdək
    ocr_max_pages: int = _int("OCR_MAX_PAGES", 20)
    pdf_text_min_chars: int = _int("PDF_TEXT_MIN_CHARS", 200)  # bundan azdırsa -> skan sayılır

    # --- Layout analizi (kart tapan OCR, ingestion/layout.py) ---
    layout_enabled: bool = _bool("LAYOUT_ENABLED", True)
    # Səhifədə bundan az kart tapılsa, bu, kartlı kataloq deyil -> adi OCR
    layout_min_cards: int = _int("LAYOUT_MIN_CARDS", 3)
    # Layout üçün render miqyası. 3.0 ölçülüb: 2.0-da qiymət rəqəmləri qarışır.
    layout_scale: float = _float("LAYOUT_SCALE", 3.0)
    max_upload_mb: int = _int("MAX_UPLOAD_MB", 40)

    # --- Scraping ---
    request_delay_seconds: float = _float("REQUEST_DELAY_SECONDS", 2.0)
    request_timeout_seconds: int = _int("REQUEST_TIMEOUT_SECONDS", 30)
    user_agent: str = _str("USER_AGENT", "BasketIQ-Student-Project/1.0")

    # Headless Chrome (ingestion/browser.py). Lokalda boş - Selenium Manager
    # quraşdırılmış Chrome-u özü tapır. Docker-də Dockerfile verir: Debian-ın
    # `chromium` + `chromium-driver` paketləri.
    chrome_binary: str = _str("CHROME_BIN", "")
    chromedriver_path: str = _str("CHROMEDRIVER_PATH", "")

    # --- Səs (Telegram + Whisper) ---
    telegram_bot_token: str = _str("TELEGRAM_BOT_TOKEN", "")
    whisper_model: str = _str("WHISPER_MODEL", "small")
    # Regex əmri tanımayanda LLM-ə müraciət edilsinmi?
    # Ölçülüb: bu çağırış 10-35 saniyə çəkir. Sürət vacibdirsə söndür -
    # o zaman yalnız şablon əmrlər işləyəcək, amma cavab dərhal gələcək.
    voice_llm_fallback: bool = _bool("VOICE_LLM_FALLBACK", True)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def ensure_dirs(self) -> None:
        """Lazımi qovluqlar yoxdursa yaradılır."""
        for path in (self.data_dir, self.raw_dir, self.text_dir,
                     self.data_dir / "cache" / "extract",
                     self.media_dir / "images" / "ads",
                     self.media_dir / "images" / "products",
                     self.media_dir / "product_images"):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
