# BasketIQ — FastAPI + OCR
#
# NİYƏ İKİ MƏRHƏLƏ YOX, BİR MƏRHƏLƏ?
# Çox mərhələli build kompilyasiya tələb edən layihələrdə faydalıdır. Burada
# bütün asılılıqlar hazır wheel-dir (pypdfium2, pillow, lxml) - ayrı build
# mərhələsi image-i kiçiltməz, yalnız Dockerfile-ı mürəkkəbləşdirərdi.
#
# NİYƏ slim, alpine YOX?
# Alpine musl libc işlədir; pillow və lxml üçün hazır wheel yoxdur və hər
# build-da mənbədən kompilyasiya olunur (dəqiqələr). Debian slim-də hamısı
# hazır gəlir.

FROM python:3.13-slim

# Tesseract yalnız BINARY kimi lazımdır - dil faylları (aze/rus/tur) layihənin
# `data/tessdata` qovluğundadır və image-ə birlikdə düşür. Ona görə
# `tesseract-ocr-aze` paketi quraşdırılmır: versiya fərqi olmasın.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Asılılıqlar koddan ƏVVƏL kopyalanır: kod dəyişəndə pip qatı keşdən gəlir
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Yazılan hər şey buraya - deployment-də volume kimi bağlanır.
# Image-in içindəki `data/` yalnız tessdata üçün qalır.
ENV DATA_DIR=/data \
    TESSDATA_DIR=data/tessdata \
    APP_ENV=production \
    APP_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data/raw /data/text /data/cache/extract

EXPOSE 8000

# Konteynerin sağlamlığı: /health həm bazanı, həm Ollama əlçatanlığını yoxlayır.
# start-period böyükdür, çünki ilk qalxışda DB sxemi yaradılır.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
