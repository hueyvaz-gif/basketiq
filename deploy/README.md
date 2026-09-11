# DigitalOcean deployment

## Əvvəlcə dürüst hesab: bu neçəyə başa gəlir?

LLM serverdə işləmir: **Claude API** (`LLM_PROVIDER=claude`) əsasdır və
Ollama-dan ~37 dəfə sürətlidir (bir kataloq sətri 1.7 san vs 64 san, ölçülüb).
Ona görə RAM-ı LLM yox, **mağaza qatının headless Chrome-u** müəyyən edir —
gündəlik qiymətlər (Wolt) brauzerlə çəkilir.

Ölçülüb (lokal Docker, 2026-09-11):

| Nə | Yaddaş |
|---|---|
| BasketIQ serveri, boşda | ~100 MB |
| Chrome qalxanda | 171 MB |
| Chrome real Wolt səhifəsində (gündəlik çəkiliş) | **665 MB pik** |
| OCR, kataloq yükləyəndə | +150–300 MB |
| n8n (`--profile n8n`) | ~250 MB (təxmini) |
| Ubuntu + Docker | ~300 MB (təxmini) |

| Droplet | Aylıq (təxmini) | İşləyirmi? |
|---|---|---|
| 1 GB / 1 vCPU | ~$6 | ❌ Chrome çəkilişi (665 MB) + sistem sığmır |
| **2 GB / 2 vCPU** | **~$18** | ✅ **tövsiyə** — çəkiliş, OCR, n8n eyni anda |
| 2 GB / 1 vCPU | ~$12 | ✅ işləyir, çəkiliş və OCR yavaş |
| 8 GB + Ollama `qwen3:4b` (`--profile ollama`) | ~$48 | ✅ yalnız LLM-i serverin öz CPU-sunda istəsən (~10 san/sətir) |

Qiymətlər DigitalOcean-ındır və dəyişə bilər — götürməzdən əvvəl yoxla. Disk
problem deyil: image Chromium ilə 1.79 GB, data ~40 MB. Ollama profili əlavə
~9 GB image + 2.6 GB model istəyir.

## Addımlar

### 1. Droplet

Ubuntu 24.04, **2 GB RAM / 2 vCPU** (yuxarıdakı hesab). Yaradıldıqdan sonra:

```bash
ssh root@<IP>
adduser basketiq && usermod -aG sudo basketiq
# 2 GB swap: Chrome çəkilişi və OCR eyni anda düşəndə yaddaş qoruyucusu
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### 2. Docker

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker basketiq
```

### 3. Layihə

```bash
su - basketiq
# Repo PRIVATE-dir. Droplet-ə yalnız BU repoya, yalnız OXUMAQ icazəsi olan açar:
ssh-keygen -t ed25519 -f ~/.ssh/basketiq_deploy -N ""
cat ~/.ssh/basketiq_deploy.pub   # GitHub → repo Settings → Deploy keys → Add ("write" işarələnmir)
git config --global core.sshCommand "ssh -i ~/.ssh/basketiq_deploy"   # sonrakı `git pull` üçün də
git clone git@github.com:hueyvaz-gif/basketiq.git basketiq && cd basketiq
cp .env.example .env
nano .env
```

`.env`-də **mütləq** dəyişilməli sətirlər:

```ini
APP_ENV=production
INGEST_API_KEY=<uzun təsadüfi sətir>     # openssl rand -hex 24
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=<açar>                  # console.anthropic.com -> API Keys
TESSERACT_CMD=                            # Linux-da boş: binary PATH-dədir
# ADMIN_ENABLED=1                         # reklamları serverdə idarə etmək üçün
```

Chromium yollarını (`CHROME_BIN`, `CHROMEDRIVER_PATH`) `.env`-ə **yazma**:
onları `Dockerfile` və `docker-compose.yml` verir; `.env`-dəki boş dəyər
image-in yolunu ezib brauzeri tapılmaz edərdi.

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
docker compose up -d                  # yalnız BasketIQ - Ollama və n8n seçimlidir
curl localhost:8000/health            # "status": "ok", llm.status: "claude"
```

Gündəlik avtomatik çəkiliş (n8n): `docker compose --profile n8n up -d`.

LLM-i serverin öz CPU-sunda istəsən (8 GB droplet):

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull qwen3:4b     # ~2.6 GB, bir dəfə
```

Onda `/health`-də `"model_available": true` görünməlidir — `false`-dursa model
çəkilməyib (aşağıda «Bilinən problem»).

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
baza, xam kataloqlar, OCR mətni, LLM keşi və şəkillər (`/data/media`: reklam
kreativləri, məhsul fotoları, kataloq kəsikləri — `MEDIA_DIR`). Şəkillər əvvəl
`app/static`-də, yəni image-in içində idi və hər yeniləmədə silinirdi.

Volume-un adı `docker-compose.yml`-də **sabitdir** (`name: basketiq_data`).
Olmasa compose onu qovluq adı ilə prefiksləyir (`basketiq_basketiq_data`) və
aşağıdakı əmrlər mövcud olmayan — yəni boş yeni — volume-u arxivləyərdi.

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

### İlk deploy: lokal datanı serverə daşımaq

Baza və şəkillər repoda **yoxdur** (`.gitignore`) — təmiz `git clone`-dan sayt
boş açılır, reklamın şəkli 404 olur. Lokal datanı volume-un quruluşunda bir
arxivə yığ:

```bash
# Lokal maşında, layihə qovluğunda
python -m tools.export_data           # -> basketiq-data.tar.gz + sha256
scp basketiq-data.tar.gz basketiq@<IP>:~/basketiq/
ssh basketiq@<IP> "sha256sum ~/basketiq/basketiq-data.tar.gz"   # alətin çap etdiyi ilə eyni olmalıdır
```

Arxivdə: baza, xam kataloqlar (`raw/`), OCR mətni (`text/`), LLM keşi (`cache/`)
və şəkillər (`media/`). Əl ilə `cp` niyə kifayət deyil — `tools/export_data.py`
başlığında: baza ANLIQ NÜSXƏ ilə götürülür (işləyən server yazsa belə bütöv
qalır), kataloq yolları Windows formatından (`raw\x.pdf`) Linux-da işləyən
`raw/x.pdf`-ə çevrilir (yalnız arxivdə), sonda arxiv açılıb bazanın istinad
etdiyi hər faylın yerində olduğu yoxlanılır. Arxiv `.gitignore` və
`.dockerignore`-dadır — repo qovluğunda dursa da image-ə düşmür.

Serverdə — baza açıq ikən üzərinə yazılmasın deyə əvvəl dayandır:

```bash
docker compose stop basketiq
docker run --rm -v basketiq_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/basketiq-data.tar.gz -C /data
docker compose up -d basketiq
```

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
| Image qurulur (Chromium ilə 1.79 GB, 235 san) | `docker build`, `docker images` (2026-09-11) |
| Chromium konteynerdə işləyir | Chromium 152 + eyni versiyalı chromedriver (Debian 13); `shop._new_driver()` real Wolt səhifəsini açdı — 24 məhsul kartı, pik 665 MB |
| Ollama-sız `/health` | Claude aktiv, Ollama yox → HTTP 200, `"status": "ok"`, `llm.status: "claude"` |
| Compose profilləri | defolt `up` → yalnız `basketiq`; `--profile ollama` → `basketiq ollama` |
| `.env` Chromium yolunu ezmir | `docker compose config` → `CHROME_BIN: /usr/bin/chromium` (`environment`-dən) |
| Konteyner sağlamdır | `HEALTHCHECK` → `healthy` |
| OCR konteynerdə işləyir | nümunə kataloq yükləndi, 8 sətir çıxdı |
| Azərbaycan dil faylları | `data/tessdata` image-dədir, `TESSDATA_DIR` göstərir |
| `APP_ENV=production` API açarı tələb edir | açarsız `POST /api/scrape/araz` → **401** |
| Data qalıcı volume-dadır | `DATA_DIR=/data` |
| Şəkillər konteyner yenidən yaradılanda qalır | kreativ yükləndi → `/data/media/images/ads` → konteyner silinib yenidən yaradıldı → eyni URL yenə **200** (2026-09-11) |
| Lokal şəkillər image-ə düşmür | image-də `images/ads`-da yalnız 2 nümunə, `product_images` və `images/products` boş |
| Ollama daxili şəbəkədən əlçatandır | `/health` → `reachable: true` |
| compose sintaksisi | `docker compose config` |

| Sınanmayıb | Səbəb |
|---|---|
| Real DigitalOcean droplet | hesab və ödəniş tələb edir |
| Caddy + Let's Encrypt | real domen lazımdır |
| `ollama pull` konteynerdə | 2.6 GB endirmə; model lokal maşında onsuz da var |

## Bilinən problem: `model_available: false` (yalnız `--profile ollama`)

Ən çox rast gəlinən hal. Səbəblər:

1. `ollama pull` edilməyib → `docker compose exec ollama ollama pull qwen3:4b`
2. `.env`-də `OLLAMA_MODEL` başqa modeldir (məsələn defolt `qwen3:8b`)
3. Ollama konteyneri qalxmayıb → `docker compose logs ollama`

`/health` bunların hamısını göstərir: `installed_models` siyahısı da qaytarılır.
