# n8n avtomatlaşdırması

BasketIQ-un gündəlik işini n8n idarə edir: kataloqu çək → AI ilə emal et →
səbəti müqayisə et → hesabat hazırla.

## Niyə n8n? Niyə sadəcə cron deyil?

Cron skripti də bu işi görərdi. Amma n8n-in üstünlüyü **görünürlükdür**: hansı
addımın nə qaytardığı, harada qırıldığı, neçə saniyə çəkdiyi interfeysdə
görünür. Bu, uzun sürən (OCR + LLM) zəncirlərdə skript loqlarından qat-qat
faydalıdır. Üstəlik "səhər 7-də işlə" qaydası koda yazılmır — dəyişmək üçün
deploy lazım gəlmir.

## İşə salmaq

```bash
docker run -d --name basketiq-n8n -p 5678:5678 \
  -e GENERIC_TIMEZONE=Asia/Baku \
  -e N8N_SECURE_COOKIE=false \
  -e BASKETIQ_URL=http://host.docker.internal:8000 \
  -e INGEST_API_KEY=dev-secret-change-me \
  -v basketiq_n8n_data:/home/node/.n8n \
  -v "<layihə yolu>/n8n":/workflows \
  docker.n8n.io/n8nio/n8n:latest
```

Aç: <http://localhost:5678>

**`host.docker.internal` nədir?** n8n konteynerin içindədir, BasketIQ isə host
maşında. Konteyner üçün `localhost` — konteynerin özüdür, ona görə host-a bu ad
ilə müraciət olunur. Linux serverdə (DigitalOcean) bunun əvəzinə `--network host`
və ya docker-compose servis adı işlədilir.

## Workflow-u idxal etmək

İnterfeys üzərindən: **Workflows → Import from File → `basketiq-gunluk.json`**

Və ya konsoldan (sınanıb, n8n 2.27.5):

```bash
docker cp n8n/basketiq-gunluk.json <konteyner>:/tmp/wf.json
docker exec <konteyner> n8n import:workflow --input=/tmp/wf.json
```

Üç tələ:

1. **`id` sahəsi məcburidir.** Faylda `"id": "basketiqGunluk01"` var; olmasa CLI
   `SQLITE_CONSTRAINT: NOT NULL constraint failed: workflow_entity.id` verir.
   (İnterfeysdən idxal edəndə bu tələb yoxdur.)
2. **Git Bash yolu çevirir.** `/tmp/wf.json` avtomatik Windows yoluna çevrilir və
   fayl tapılmır. Qarşısını almaq üçün: `export MSYS_NO_PATHCONV=1`.
3. **İdxal workflow-u HƏMİŞƏ deaktiv edir** — konsolda
   `Deactivating workflow "..."` yazır. Fayla `"active": true` əlavə etmək
   KÖMƏK ETMİR (sınandı). `n8n update:workflow --active=true` isə yalnız
   bazadakı bayrağı dəyişir və işləyən proses onu görmür — n8n özü belə
   deyir: *«Changes will not take effect if n8n is running»*. Bu, ən pis
   vəziyyəti yaradır: interfeysdə açar YANIQ görünür, amma cədvəl işə
   düşmür.

   **Yeganə etibarlı yol:** idxaldan sonra interfeysdən (<http://localhost:5678>)
   workflow-u açıb sağ yuxarıdakı **Active** açarını əl ilə çevirmək — trigger
   məhz onda canlı qeydiyyata düşür. Bu, hər idxaldan sonra təkrarlanmalıdır.

### Konsoldan işə salmaq

**TƏLƏ: `execute` YALNIZ BİRİNCİ TRIGGER-İ İŞLƏDİR.** Axında iki cədvəl
trigger-i var (07:00 kataloq, 05:30 mağaza). Ölçüldü (2026-09-10):

```
docker exec ... n8n execute --id basketiqGunluk01
  -> trigger: «Her seher 07:00»
  -> işləyən node-lar: Konfiqurasiya, Kataloqu cek, Yeni kataloq varmi,
     Deyisiklik yoxdur, Bagli menbeni yoxla, Menbe hesabati
  -> «Magaza qiymetlerini cek» İŞƏ DÜŞMÜR
```

Yəni CLI ilə mağaza zəncirini yoxlamaq mümkün deyil. İki yol var:

- **İnterfeysdən:** workflow-u aç, `Her seher 05:30` node-unu seç və
  «Execute workflow» de - yalnız həmin qol işləyir.
- **Endpoint-i birbaşa çağır** (node onsuz da bunu edir):

  ```bash
  curl -X POST "http://127.0.0.1:8000/api/shop/bravo"        -H "X-API-Key: dev-secret-change-me" --max-time 5400
  ```

  Bu, n8n bağlantısını YOXLAMIR - yalnız işin özünü.



```bash
docker exec -e N8N_RUNNERS_BROKER_PORT=5690 -e N8N_PORT=5691 <konteyner> n8n execute --id basketiqGunluk01
```

Niyə əlavə portlar? İşləyən n8n artıq 5678/5679 portlarını tutub; `execute`
əmri öz task broker-ini qaldırmağa çalışır və "port is already in use" deyir.

Niyə `Elle isle sal` (Execute Workflow Trigger) node-u var? CLI `execute` Schedule
Trigger-i başlanğıc nöqtəsi saymır — "Missing node to start execution" deyir.
Bu node həm CLI sınağı, həm də başqa workflow-dan çağırış üçün lazımdır.

## Sınaq nəticəsi

Hər iki budaq real olaraq işlədilib (n8n 2.27.5, Docker):

| Budaq | Nəticə |
|---|---|
| Yeni kataloq yoxdur | `BasketIQ: yeni kataloq yoxdur (1 otürüldü).` |
| Yeni kataloq var | kataloq çəkildi → OCR → 10 sətir LLM ilə emal → 10 məhsul → səbət müqayisəsi → hesabat |

## `basketiq-gunluk.json` — nə edir

```
Hər səhər 07:00 (və ya "Elle isle sal")
   → Konfiqurasiya                           URL, açar, mənbə, limitlər - BİR yerdə
   → POST /api/scrape/araz?max_pages=2        kataloqu çək (robots.txt-ə tabe)
   → IF ingested.length > 0                  yeni kataloq varmı?
        BƏLİ  → POST /api/catalogs/{id}/extract?limit=10    AI ilə məhsullar
              → GET  /api/basket/compare                    səbət müqayisəsi
              → Code: hesabat mətni
        XEYR  → Code: "yeni kataloq yoxdur"
```

**Niyə IF node lazımdır?** Kataloq həftədə bir dəfə dəyişir, workflow isə hər gün
işləyir. Yəni günlərin çoxunda scraper "bu URL artıq çəkilib" deyib boş qayıdır.
Bu, **xəta deyil** — normal haldır. IF olmasa, növbəti addım `ingested[0]`
üzərində qırılar və hər səhər saxta xəta bildirişi gələrdi.

**Niyə `$env` yox, Konfiqurasiya node-u?** n8n-də environment dəyişənlərinə giriş
təhlükəsizlik üçün bloklana bilir (`N8N_BLOCK_ENV_ACCESS_IN_NODE`). Set node isə
həmişə işləyir və istifadəçi URL-i dəyişmək üçün yalnız bir yerə baxır.

**Niyə `max_pages=2` və `limit=10`?** GPU-suz maşında hər OCR səhifəsi ~20 saniyə,
hər LLM sətri ~10 saniyədir. Limitsiz işləsə, workflow saatlarla asılı qalar.
Real serverdə bu rəqəmlər artırıla bilər.

**Timeout.** HTTP node-larda `timeout` böyük qoyulub (10-15 dəqiqə). n8n-in
defolt timeout-u 5 dəqiqədir və OCR ondan uzun çəkə bilər — node "uğursuz"
görünər, halbuki BasketIQ işini davam etdirir.

## Bildiriş əlavə etmək

Sonuncu Code node `hesabat` sahəsi qaytarır. Ona istənilən çıxış node-u
qoşula bilər: Telegram, Gmail, Slack, Webhook. Layihədə konkret provayder
seçilməyib ki, hesabat üçün hesab açmaq məcburiyyəti olmasın.

## MCP ilə birləşmə (AI Agent)

BasketIQ MCP serveri `http://host.docker.internal:8000/mcp` ünvanındadır.
n8n-də AI Agent qurmaq üçün:

1. **Chat Trigger** node əlavə et
2. **AI Agent** node əlavə et
3. Agent-in *Chat Model* girişinə **Ollama Chat Model** qoş
   (Base URL: `http://host.docker.internal:11434`, model: `qwen3:4b`)
4. Agent-in *Tool* girişinə **MCP Client Tool** qoş
   (Endpoint: `http://host.docker.internal:8000/mcp`, Transport: HTTP Streamable)

Bundan sonra çatda "səbətim harada ucuzdur?" yazanda model özü `compare_basket`
alətini çağırır. Alət siyahısını əl ilə yazmaq lazım deyil — MCP onu özü elan edir.

**Gözlənti:** `qwen3:4b` CPU-da saniyədə ~4.5 token yazır, ona görə agent cavabı
10-30 saniyə çəkəcək. Nümayiş üçün kifayətdir, real istifadə üçün model serverdə
işləməlidir.

## Server 07:00-da işlək olmalıdır

Axın `host.docker.internal:8000` ünvanına sorğu göndərir. BasketIQ serveri
işləmirsə, zəncir ilk addımda qırılır — və Windows-da bu, xüsusilə xəbisdir:
port 8000-i Docker-in başqa konteyneri də dinləyir, ona görə cavab
«bağlantı yoxdur» yox, **404** olur (bax `logs/sources.md` və layihə kökündəki
qeydlər).

Ona görə server Task Scheduler ilə avtomatik qaldırılır:

```powershell
# Qeydi yaratmaq (bir dəfə)
$root = "<layihə yolu>"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$root\scripts\start_server.ps1`"" `
  -WorkingDirectory $root
Register-ScheduledTask -TaskName "BasketIQ Server" -Action $action `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME), `
           (New-ScheduledTaskTrigger -Daily -At 06:50) `
  -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew) `
  -RunLevel Limited
```

**İki trigger var və hər ikisi lazımdır:** girişdə (kompüter açılanda) və
**06:50-də** (n8n 07:00-da çağırır; server gün ərzində düşübsə, geri qalxır).

`scripts/start_server.ps1` özü **idempotentdir**: `127.0.0.1:8000` artıq
dinlənilirsə heç nə etmir. Yoxlama məhz `127.0.0.1`-ə baxır — `0.0.0.0:8000`
Docker-indir və onun olması bizim serverin işləməsi demək deyil.

Yoxlamaq / silmək:

```powershell
Get-ScheduledTaskInfo -TaskName "BasketIQ Server"     # son nəticə kodu 0 olmalıdır
Start-ScheduledTask   -TaskName "BasketIQ Server"     # əl ilə işə salmaq
Unregister-ScheduledTask -TaskName "BasketIQ Server" -Confirm:$false
```
