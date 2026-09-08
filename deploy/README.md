# DigitalOcean deployment

## Əvvəlcə dürüst hesab: bu neçəyə başa gəlir?

Layihənin ağır hissəsi FastAPI deyil, **LLM-dir**. Qiyməti o müəyyən edir.

| Konfiqurasiya | RAM | Aylıq (təxmini) | İşləyirmi? |
|---|---|---|---|
| Yalnız BasketIQ (LLM xaricdə) | 1 GB | ~$6 | ✅ dashboard, scraping, OCR işləyir; AI çıxarışı yox |
| BasketIQ + Ollama `qwen3:4b` | 8 GB | ~$48 | ✅ hər şey işləyir, CPU-da yavaş (~10 san/sətir) |
| BasketIQ + Ollama, 4 GB | 4 GB | ~$24 | ⚠️ model güclə sığır, OCR ilə eyni vaxtda swap-a düşür |

`qwen3:4b` diskdə ~2.6 GB, yüklənəndə ~4 GB RAM tutur. OCR də eyni anda
150-300 MB istəyir. Ona görə **8 GB tövsiyə olunur**, 4 GB isə sərhəddədir.

**Tələbə üçün praktik yol:** əvvəlcə **1 GB droplet** ($6) götür, `APP_ENV=production`
ilə dashboard və scraping-i işlət. AI çıxarışını lokal maşında (və ya lazım
olanda müvəqqəti böyük droplet-də) apar. Kod dəyişmir — yalnız
`OLLAMA_BASE_URL` fərqlidir.

## Addımlar

### 1. Droplet

Ubuntu 24.04, ən azı 2 vCPU. Yaradıldıqdan sonra:

```bash
ssh root@<IP>
adduser basketiq && usermod -aG sudo basketiq
```

### 2. Docker

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker basketiq
```

### 3. Layihə

```bash
su - basketiq
git clone <repo> basketiq && cd basketiq
cp .env.example .env
nano .env
```

`.env`-də **mütləq** dəyişilməli sətirlər:

```ini
APP_ENV=production
INGEST_API_KEY=<uzun təsadüfi sətir>     # openssl rand -hex 24
OLLAMA_MODEL=qwen3:4b
TESSERACT_CMD=                            # Linux-da boş: binary PATH-dədir
```

`TESSERACT_CMD` niyə boş? Windows-da tam yol lazımdır (`C:\Program Files\...`),
Linux konteynerində isə `tesseract` elə PATH-dədir. Dolu qalsa, konteyner
Windows yolunu axtarıb OCR-də qırılar.

### 3b. Səs bonusu lazımdırsa (seçimli)

```bash
docker build --build-arg WITH_VOICE=true -t basketiq:latest .
```

**Ölçülüb: image 684 MB → 1.25 GB.** Səs funksiyası bonusdur — dashboard,
scraping, müqayisə və MCP onsuz da işləyir. Üstəlik Whisper modeli işləyəndə
əlavə ~1 GB RAM tutur, yəni kiçik droplet-də praktik deyil. Ona görə defolt
olaraq quraşdırılmır.

Səs modulu yoxdursa `/api/voice` **503** qaytarır və nə etmək lazım olduğunu
mətndə yazır — səssiz qırılma olmur.

### 4. Qaldır

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen3:4b     # ~2.6 GB, bir dəfə
curl localhost:8000/health
```

`/health` cavabında `"model_available": true` görünməlidir. `false`-dursa
model çəkilməyib — bu, layihənin ən çox rast gəlinən deployment səhvidir və
məhz ona görə `/health` modeli ayrıca yoxlayır.

### 5. Domen və HTTPS

```bash
sudo apt install -y caddy
```

`/etc/caddy/Caddyfile`:

```
basketiq.example.com {
    # flush_interval -1 = buferləmə yoxdur.
    # SSE (AI tövsiyəsi) üçün vacibdir: buferlənsə, mətn token-token yox,
    # birdəfəyə gəlir və streaming-in bütün mənası itir.
    reverse_proxy localhost:8000 {
        flush_interval -1
    }
}
```

```bash
sudo systemctl reload caddy
```

Caddy Let's Encrypt sertifikatını özü alır. Niyə nginx yox? nginx-də eyni
nəticə üçün certbot, cron və ayrıca konfiqurasiya lazımdır; Caddy bunu bir
sətirlə edir və layihəyə öyrənmə yükü gətirmir.

### 6. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80,443/tcp
sudo ufw enable
```

**8000 portu açılmır** — ona yalnız Caddy localhost-dan müraciət edir.
Ollama portu da (11434) `docker-compose.yml`-də qəsdən dərc olunmayıb:
autentifikasiyasız LLM serveri internetdə qalmamalıdır.

## Data və ehtiyat nüsxə

Yazılan hər şey **tək volume-dadır** (`basketiq_data` → konteynerdə `/data`):
baza, xam kataloqlar, OCR mətni, LLM keşi.

```bash
# Ehtiyat nüsxə
docker run --rm -v basketiq_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/basketiq-$(date +%F).tar.gz -C /data .

# Bərpa
docker run --rm -v basketiq_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/basketiq-2026-09-07.tar.gz -C /data
```

Niyə tək volume? Data üç yerə dağılsaydı (baza ayrı, fayllar ayrı, keş ayrı),
ehtiyat nüsxə natamam ola bilərdi: baza kataloqa istinad edir, fayl isə yoxdur.

## Yeniləmə

```bash
git pull
docker compose build basketiq
docker compose up -d basketiq
```

Baza sxemi `CREATE TABLE IF NOT EXISTS` və `_migrate()` ilə özü yenilənir —
data silmək lazım deyil.

## Nə sınanıb, nə sınanmayıb

| Yoxlanılıb (lokal Docker) | Necə |
|---|---|
| Image qurulur (684 MB; səslə 1.25 GB) | `docker build` |
| Konteyner sağlamdır | `HEALTHCHECK` → `healthy` |
| OCR konteynerdə işləyir | nümunə kataloq yükləndi, 8 sətir çıxdı |
| Azərbaycan dil faylları | `data/tessdata` image-dədir, `TESSDATA_DIR` göstərir |
| `APP_ENV=production` API açarı tələb edir | açarsız `POST /api/scrape/araz` → **401** |
| Data qalıcı volume-dadır | `DATA_DIR=/data` |
| Ollama daxili şəbəkədən əlçatandır | `/health` → `reachable: true` |
| compose sintaksisi | `docker compose config` |

| Sınanmayıb | Səbəb |
|---|---|
| Real DigitalOcean droplet | hesab və ödəniş tələb edir |
| Caddy + Let's Encrypt | real domen lazımdır |
| `ollama pull` konteynerdə | 2.6 GB endirmə; model lokal maşında onsuz da var |

## Bilinən problem: `model_available: false`

Ən çox rast gəlinən hal. Səbəblər:

1. `ollama pull` edilməyib → `docker compose exec ollama ollama pull qwen3:4b`
2. `.env`-də `OLLAMA_MODEL` başqa modeldir (məsələn defolt `qwen3:8b`)
3. Ollama konteyneri qalxmayıb → `docker compose logs ollama`

`/health` bunların hamısını göstərir: `installed_models` siyahısı da qaytarılır.
