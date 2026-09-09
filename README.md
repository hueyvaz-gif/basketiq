# BasketIQ

Supermarket endirim kataloqlarını (PDF / şəkil) avtomatik oxuyan, məhsulları
marketlər arasında uyğunlaşdıran və **"səbətini harada al"** sualına rəqəmlə
cavab verən AI analitika paneli.

## Problem

Marketlər həftəlik endirimləri maşın-oxunaqlı olmayan **PDF/şəkil kataloq**
şəklində yayır. "Bu həftə süd, düyü, yağ harada ucuzdur?" sualına cavab tapmaq
üçün insan 3-4 kataloqu əl ilə vərəqləməlidir.

## Həll

```
market saytı
   → requests + BS4           kataloq PDF-ini tap və endir (robots.txt-ə tabe)
kataloq (PDF/JPG)
   → pypdf / pytesseract      mətn çıxarma
   → layout analizi           qlyanslı kataloqda "kart" tapma
   → cleaning                 zibil sətirlərin atılması
   → LangChain LCEL .batch()  → Claude (ehtiyat: Ollama)  struktur JSON
   → hibrid matching          eyni məhsul, fərqli market
   → SQLite                   unit_price (1 kq / 1 L)
   → FastAPI + Dashboard      müqayisə, trend, AI tövsiyəsi
```

## Texnologiyalar

LangChain (LCEL, batch, astream, Output Parser) · Ollama + Qwen · n8n · MCP ·
BeautifulSoup / Selenium · pypdf · pytesseract · Whisper + Telegram ·
FastAPI · SQLite · Docker · DigitalOcean

## Quraşdırma

```bash
py -3.13 -m venv .venv          # Python 3.13 (3.14-də bəzi paketlərin wheel-i yoxdur)
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Səsli əmrlər (bonus) istəyirsənsə - ayrıca:
pip install -r requirements-voice.txt

copy .env.example .env          # sonra .env-i redaktə et
ollama list                     # quraşdırılmış modeli .env-də OLLAMA_MODEL kimi yaz

uvicorn app.main:app --reload
```

Aç: <http://localhost:8000> · Sağlamlıq: <http://localhost:8000/health>

### Tesseract (OCR)

Windows üçün Tesseract-ı quraşdır və `.env`-də `TESSERACT_CMD` yolunu göstər.
**Dil paketi seçmək lazım deyil** — `aze`, `rus`, `tur` faylları layihənin
`data/tessdata/` qovluğundadır (aşağıda "OCR dil faylları" bölməsinə bax).

Linux/Docker-də `TESSERACT_CMD` **boş qalmalıdır**: orada binary PATH-dədir.

## Test

```bash
pytest -q
```

## AI zənciri (LangChain LCEL)

```
prompt | ChatOllama(format="json") | qısa açarların açılması | PydanticOutputParser
```

Ölçülmüş qərarlar (`tools/profile_llm.py`):

| Qərar | Səbəb | Nəticə |
|---|---|---|
| LLM-dən qiymət soruşulmur | rəqəm uydurma riski; regex uydurmur | hallucination = 0 |
| `reasoning=False` | qwen3-ün `<think>` rejimi CPU-da çox baha | 2-4x sürət |
| Kompakt format təlimatı | standart təlimat 1444 simvol, bizimki 241 | 37 → 12 san/sətir |
| Qısa açarlar + rəqəm kateqoriya | cavab yazma 4.5 tok/san — əsas əngəl | 50 → 41 token |
| Disk keşi | prompt təkrar sınananda yenidən hesablanmasın | 50 san → 0.003 san |
| Sətir-sətir emal (qrup yox) | qrupda cavab sırası pozula bilər | qiymət düz məhsula yapışır |

## Mənbələr (ölçülüb, fərz edilməyib)

`tools/check_source.py` hər namizəd saytı yoxlayır: robots.txt, statik/dinamik,
kataloq linki, PDF-də text layer. Mağaza qatı üçün `--all` rejimi çəkmə
pilləsini də ölçür (JSON/XHR → BeautifulSoup → Selenium).

**İki fərqli qat var və onlar qarışdırılmır:**

| Qat | Mənbə | Tezlik | Nə verir |
|---|---|---|---|
| Baza qiymət | onlayn mağazanın kateqoriya səhifələri | gündəlik | məhsulun adi qiyməti |
| Endirim iddiası | həftəlik kataloq (PDF/şəkil, OCR yolu) | həftəlik | «9.99 → 5.99» iddiası |

Kataloqun «köhnə qiymət» iddiasını yenə kataloqla təsdiqləmək dairəvi
məntiqdir — ona görə iddia ilk qatdakı öz müşahidələrimizlə yoxlanılır.

### Ölçmə nəticəsi (2026-09-08)

| Market | robots.txt | Kataloq qatı | Mağaza qatı | Qərar |
|---|---|---|---|---|
| **Araz** | icazə ✓ | 1 PDF × 54 səh. (statik HTML) | **yox** — data ünvanı qadağan | **yalnız kataloq mənbəyi** |
| **Bravo** | icazə ✓ | yox — PDF linki tapılmadı | Umico üzərindən (Selenium) | **yalnız mağaza mənbəyi** |
| Bazarstore | icazə ✓ | yox | yox — sayt baxımdadır | gözləyir |

**Araz-ın mağaza qatı niyə yoxdur?** `arazmarket.az/robots.txt` `Disallow: /api/`
və `Disallow: /_next/` yazır — yəni səhifənin data ünvanları qadağandır.
Qiymət ilk HTML-də görünmür (1.46 MB fayl, 634 simvol mətn, məzmun yerinə
`Loading...`), ona görə BeautifulSoup da işləmir. Selenium **qəsdən**
işlədilmir: brauzer səhifəni render edəndə həmin qadağan ünvanları özü çağırır,
yəni «yalnız səhifəni açdım» deyib qadağanı dolayı yolla keçmək olardı.

**Market siyahısı bağlıdır.** Layihənin marketləri `app/stores.py`-dədir və
cəmi dörddür: Araz Market, Bravo Market, Bazar Store, Rahat Market. Siyahıdan
kənar market nə mənbə kimi çəkilir, nə də UI-da görünür; bazaya keçmiş belə
sətirlər `tools/purge_store.py` ilə tamamilə silinir (ehtiyat nüsxə ilə).

**«Bravo qadağalıdır» qeydi səhv idi.** Əvvəlki cədvəldə Bravo `qadağa ✗` kimi
yazılmışdı. Yoxlanıldı: `bravosupermarket.az/robots.txt` faktiki olaraq
`Allow: /` deyir və yalnız bir alt-yolu (`/bravo.jis.az/`) bağlayır. Səhvin
mənbəyi `urllib.robotparser` idi — təfərrüat `ingestion/robots.py`-ın başında.
Bravo kataloq mənbəyi olmamasının səbəbi icazə deyil: `special-offers` səhifəsi
Angular-dır və statik HTML-də bir dənə də PDF/şəkil linki yoxdur.

Araz-ın kataloq səhifəsi statik HTML olduğu üçün **Selenium defolt
işlədilmir** — `requests` + BeautifulSoup kifayətdir. Selenium yalnız statik
yol boş qayıdanda işə düşür (`--selenium`): brauzer qaldırmaq ~3-5 saniyədir və
serverdə ayrıca Chrome tələb edir. Eyni "əvvəlcə ucuz yolu sına" prinsipi
OCR-da da var.

```bash
python tools/check_source.py --all         # mağaza qatı: pillə ölçmə cədvəli
python tools/scrape.py                     # kataloq mənbələri + robots yoxlaması
python tools/scrape.py araz --dry-run      # yalnız linkləri göstər
python tools/scrape.py araz --pages 2      # endir + OCR + DB
```

Təkrar yoxlaması iki pillədədir: əvvəlcə **URL** (9 MB-lıq PDF-i boş yerə
endirməmək üçün), sonra fayl **hash**-i.

## robots.txt oxuyucusu — `urllib`-dəki iki səhv

Layihənin ən sərt qaydası budur: **`robots.txt` qadağan edirsə, çəkmirik.**
Ona görə həmin faylı DÜZGÜN oxumaq funksional tələbdir, detal deyil.

`urllib.robotparser` bu iş üçün yararsız çıxdı. Hər iki səhv 2026-09-08-də
ölçülüb və hər ikisi eyni qaydaya toxunur:

**1. Kitabxana öz adı ilə gedir və 403 alır.** `RobotFileParser.read()` faylı
urllib ilə çəkir, urllib isə özünü `Python-urllib/3.x` kimi təqdim edir.
`umico.az` və `bravosupermarket.az` bu ada **403** qaytarır — kitabxana isə
403-ü «bütün sayt qadağandır» kimi qeyd edir (`disallow_all = True`).

Nəticə: `Allow: /` yazan sayt bizim kodda QADAĞA görünürdü.
**README-nin əvvəlki versiyasında «Bravo — qadağa ✗» qeydi məhz bu səhvin
nəticəsi idi** və «ölçülmüş fakt» kimi saxlanılırdı.

**2. Kitabxana birinci uyğunluğu götürür, ən uzununu yox.**
`arazmarket.az/robots.txt`:

```
Allow: /
Disallow: /api/
```

`urllib` sətirləri sıra ilə yoxlayır, `Allow: /` hər şeyə uyğun gəlir və dərhal
«icazə var» deyir — yəni `Disallow: /api/` **heç vaxt işə düşmür**. RFC 9309
isə açıq deyir: **ən spesifik (ən uzun) qayda qalib gəlir**.

Ölçmə: köhnə kodla `https://www.arazmarket.az/api/` → `icazə=True` (yanlış),
yeni kodla → `icazə=False` (düzgün).

İkinci səhv daha təhlükəlidir: birincisi bizi lazımsız yerə məhdudlaşdırırdı,
ikincisi isə **real qadağanı görünməz edirdi**.

**Həll:** `ingestion/robots.py` — RFC 9309 semantikası (ulduz, `$` lövbəri, ən
uzun uyğunluq, `Allow` bərabərlikdə üstün). Fayl öz dürüst User-Agent-imizlə
çəkilir; sorğularımızı da elə həmin ad ilə göndəririk, gizlətmə yoxdur.
Status kodları standart üzrə oxunur: 401/403 → hamısı qadağan, 404/410 →
icazə, 5xx → naməlum.

Modul **şəbəkəyə çıxmır** — `parse()` mətn qəbul edir, ona görə 12 test real
saytdan asılı deyil. Mutasiya ilə yoxlanılıb: «ən uzun uyğunluq» məntiqi
birinci-uyğunluğa çevriləndə 3 test, `$` lövbəri söndürüləndə 1 test düşür.

## Layout analizi — qlyanslı kataloqu oxumaq

Real kataloq **sətirlərdən ibarət deyil**, kartlar şəbəkəsidir: ad yuxarı solda,
qiymət aşağı sağda ayrı rəngli qutuda, aralarında məhsul şəkli. Adi sətir-əsaslı
OCR bu səhifədən **0 məhsul** çıxarır.

Həll: qiymət qutusunu **rəngə görə** tapıb kartın "lövbəri" sayırıq, sonra hər
sözü öz lövbərinə bağlayırıq.

| Qərar | Səbəb | Ölçmə |
|---|---|---|
| Qırmızı qutu = lövbər | qiymət həmişə rənglidir, mətn isə yox | 10/10 kart |
| Sözü "özündən sonrakı" lövbərə bağla | ad əvvəl, qiymət sonra oxunur | "ən yaxın" qaydası 3 kartı qarışdırırdı |
| Sarı qutuya 10% kənar | maska rəqəmin kənarını kəsir | 6/10 → 10/10 |
| Qırmızı qutuya kənar YOX | orada ağ fon rəqəmə çevrilir | 10/10 → 4/10 |
| Köhnə qiymət üçün 3 psm + süzgəc | üstündən keçən xətt rəqəmi korlayır | səhv dəyər əvəzinə `None` |
| Fonu ağ olmayan sözü at | qablaşdırma üzərindəki yazı məhsulun adı deyil | "ESKIMO", "МИРАТОРГ" atıldı |
| `char_whitelist` həmişə yaxşı deyil | LSTM-də çıxışı tamam boğa bilir | boş sətir → `'\| 199'` |

**Nəticə** (qlyanslı jurnal, səhifə 2, 10 məhsul): ad 10/10, yeni qiymət 10/10,
köhnə qiymət 10/10, ~15-30 san/səhifə.

**Bilinən məhdudiyyət:** Araz-ın dizaynında qiymət 2 ölçülü yazılır (böyük
rəqəm, sağ yuxarısında kiçik qəpik, altında ₼) və sağ sütunda qutu ümumiyyətlə
yoxdur. Orada 8 məhsuldan 5-i tapılır, qiymətlərin 4-ü düzgündür. Səhv rəqəm
yazmaqdansa `None` qaytarırıq.

Kart tapılmayan səhifədə sistem avtomatik adi OCR-a qayıdır — sadə siyahı
şəklindəki kataloq üçün düzgün cavab elə odur.

### Şəbəkədən düşən kart — sətirlərin qarışması

Səhifədə **175 qırmızı qutu** var, amma yalnız **102-sinin qiyməti oxunur**:
Araz-da qiymət ikimərtəbəli yazılır (böyük «1», sağ yuxarısında kiçik «99») və
Tesseract onu həmişə tutmur.

Əvvəl qiyməti oxunmayan qutu şəbəkədən **tamamilə çıxırdı**. Söz isə «özündən
sonrakı ilk lövbərə» bağlanır — deməli həmin kartın sözləri qonşuya axırdı:

```
«Penstore Karandaş 12 rəng Penstore Qayçı ASH Su qabi 5.79»   ← üç ayrı kart
```

Belə sətir həm LLM-i, həm də şəkil uyğunlaşdırmasını çaşdırır: məhz buna görə
«karandaş» məhsuluna **su qabının** şəkli düşmüşdü (`logs/image-check.md`).

**Düzəliş:** şəbəkə **bütün** qırmızı qutulardan qurulur. Qiymətsiz qutu kart
yaratmır, amma öz xanasını sahiblənir — sözləri qonşuya getmir, **atılır**.
Lövbərlər ölçüyə görə süzülür (`_grid_landmarks`, median ölçünün 0.6–1.6-sı),
əks halda endirim nişanı («32%» qırmızı ləkəsi) də xana tutur və qonşu kartı
boşaldır.

**Sınanan və atılan variant:** sözün lövbərdən məsafəsini `_grid_step()` ilə
məhdudlaşdırmaq. Ölçüldü — `_grid_step()` kartın eni **deyil**, qonşu qiymət
qutuları arasındakı median məsafədir və qutular yan-yana düşəndə kiçilir
(6-cı səhifədə 112, kart isə ~250 piksel). Nəticədə kartın öz sözləri kəsilirdi:
«Nestle Damak Şokolad» → «Şokolad». Sərhəd atıldı.

**Ölçmə (20 səhifə, 102 kart):**

| | Əvvəl | Sonra |
|---|---|---|
| 12 sözdən uzun kart (qarışıq sətir) | 6 | **1** |
| Ən uzun kart | 23 söz | 20 söz |
| Mətni boş kart | 14 | 15 |

---

## MCP serveri — layihəni AI agentlərinə açmaq

FastAPI endpoint-lərini insan və skript çağırır. MCP isə eyni funksiyaları
**modelin** çağıra bilməsi üçün standart formatda elan edir: alətin adı, nə
etdiyi, hansı parametrləri var. Model bu təsviri oxuyub özü qərar verir ki,
"səbətim harada ucuzdur?" sualına hansı aləti çağırmalıdır.

13 alət: `search_products`, `show_basket`, `add_to_basket`, `remove_from_basket`,
`compare_basket`, `list_sources`, `list_catalogs`, `scrape_catalog`,
`extract_catalog`, `health`, `show_profile`, `update_profile`, `recommend_plan`.

| Qərar | Səbəb |
|---|---|
| Alətlər öz məntiqini yazmır | `app/api/*` funksiyalarını çağırır — "natamam market qalib elan edilmir" qaydası bir yerdə qalır |
| Cavablar qısa mətndir, JSON deyil | alətin qaytardığı hər simvol modelin konteksinə düşür; cavab yazması 4.5 tok/san |
| Xəta mətnə çevrilir | modelə `HTTPException(404)` yox, "Kataloq tapılmadı" getməlidir — ikincidən nə edəcəyini anlayır |
| Ağır iş `anyio.to_thread`-də | MCP FastAPI ilə eyni prosesdədir; OCR-ı birbaşa çağırsaq bütün veb tətbiq donar |
| FastAPI-yə mount olunur | bir proses, bir port, bir deployment |

**Mount tələsi:** mount olunmuş ASGI tətbiqinin öz `lifespan`-ı avtomatik işə
düşmür, MCP-nin sessiya meneceri isə məhz orada başlayır. Üstəlik həmin menecer
bir nüsxədə yalnız bir dəfə işə salına bilir — ona görə `/mcp` altına nazik
proxy qoyulub və MCP tətbiqi hər start-da yenidən yaradılır.

```bash
# HTTP (n8n, uzaq klientlər) - FastAPI ilə birlikdə qalxır
uvicorn app.main:app          # -> http://localhost:8000/mcp

# stdio (Claude Desktop) - ayrı proses
python -m mcp_server.server
```

Claude Desktop üçün nümunə konfiqurasiya:
`mcp_server/claude_desktop_config.example.json`

## n8n avtomatlaşdırması

Gündəlik zəncir: kataloqu çək → AI ilə emal et → səbəti müqayisə et → hesabat.

Workflow və təlimat: [`n8n/README.md`](n8n/README.md),
fayl: `n8n/basketiq-gunluk.json`

Niyə cron skripti deyil? n8n-də hansı addımın nə qaytardığı və harada qırıldığı
görünür — OCR + LLM kimi uzun zəncirlərdə bu, loq oxumaqdan qat-qat faydalıdır.

## Profil əsaslı tövsiyə

`compare()` sualı: "hansı market ucuzdur?"
Bu bölmənin sualı isə başqadır: **"MƏNƏ nə etmək sərfəlidir?"**

Ən ucuz market həmişə doğru cavab deyil. Profil bu fərqi rəqəmə çevirir:

| Profil sahəsi | Tövsiyəni necə dəyişir |
|---|---|
| `max_stores` | 1-dirsə səbət bölünmür — bir markete gedən adama "iki marketi gəz" demək məsləhət deyil |
| `min_split_saving` | 2-ci market yalnız bu qədər qənaətə dəyərsə təklif olunur (defolt 1 AZN) |
| `weekly_budget` | cəm büdcəni aşırsa xəbərdarlıq + büdcəni yeyən 3 məhsul |
| `household_size` | 3+ nəfərdirsə daha böyük qablaşdırma yoxlanılır (**vahid qiymət** üzrə) |
| `avoid` | səbətdə istənilməyən söz varsa bildirilir |

Nümunə (real data): səbəti 2 markete bölmək **0.16 AZN** qənaət edir.
`min_split_saving = 0.50` olanda sistem **tək market** tövsiyə edir və səbəbini
yazır. `0.10` olanda isə bölünmüş plan verilir və hansı məhsulun harada
alınacağını göstərir. Yəni profil bəzək deyil — qərarı dəyişir.

**Səbəb mətni dəqiq olmalıdır.** Bölmə iki fərqli səbəbdən rədd edilə bilər:
qənaət azdır, ya da plan icazə veriləndən çox market tələb edir. Əvvəlcə hər
ikisinə eyni mətn yazılırdı — istifadəçi yanlış ayarı dəyişməyə çalışardı.
Test bunu tutdu.

**Profil AI tövsiyəsinə də ötürülür** (`ai/advisor.py`): faktlar blokunun
başına `İSTİFADƏÇİ: ...` sətri əlavə olunur. Model rəqəmləri yenə hesablamır —
sadəcə tövsiyəni istifadəçinin şəraitinə uyğunlaşdırır.

## Endirim yoxlaması — "saxta endirim" bayrağı

Kataloqda yazılır "9.99 → 5.99". Amma məhsul heç vaxt 9.99-a satılmayıbsa, bu,
endirim deyil — şişirdilmiş köhnə qiymətdir. Marketin öz rəqəminə inanmaq üçün
səbəb yoxdur; bizim isə **öz müşahidələrimiz** var.

Hökm üç deyil, **dörd** haldır:

| Hökm | Nə vaxt | Nümunə səbəb |
|---|---|---|
| **Təsdiqlənib** | bu qiyməti (±5%) əvvəllər özümüz görmüşük | "əvvəllər 9.90 AZN-ə görmüşük" |
| **Təsdiqlənməyib** | tarixçə yoxdur və ya azdır | "bu məhsulu əvvəllər görməmişik" |
| **Şübhəli** | iddia gördüyümüz maksimumdan 25%+ yüksəkdir, ya da endirim 70%-dən dərindir | "iddia 12.00, gördüyümüz maksimum 4.20" |
| **Endirim yoxdur** | köhnə qiymət göstərilməyib | — |

**Niyə "saxta" sözü hökmdə yoxdur?** Çünki iddia hüquqi məsuliyyət daşıyır,
bizim datamız isə 2-3 kataloqdur. Bilmədiyini "saxta" adlandırmaq —
faydasız xəbərdarlıqdan da pisdir. "Şübhəli" dürüstdür, "saxta" deyil.

Ayrıca `cheaper_elsewhere` yoxlanılır: endirim həqiqi ola bilər, amma qonşu
market elə həmişə daha ucuz satır — "20% endirim var, yanındakı marketdə isə
endirimsiz qiymət daha aşağıdır".

## Qiymət tarixçəsi qrafiki

`group_key` üzrə bütün müşahidələr, market üzrə ayrı xətt (Chart.js, CDN-dən).
Kitabxana yüklənməsə səhifə qırılmır — rəqəmlər cədvəldə qalır.

Bir müşahidəsi olan məhsulda qrafik çəkilmir, əvəzinə açıq yazılır:
"cəmi 1 müşahidə var, trend üçün ən azı 2 lazımdır". Tək nöqtəni trend kimi
göstərmək istifadəçini aldatmaq olardı.

## Səsli əmrlər (Telegram + Whisper)

```
Telegram səs mesajı
   → faster-whisper        səs -> mətn
   → regex təhlili         mətn -> niyyət (add / remove / show / compare / price)
   → (alınmasa) LLM        sərbəst cümlələr üçün ehtiyat yol
   → app/api/* funksiyaları     ← MCP və HTTP ilə EYNİ məntiq
```

Bot üçün `.env`-də `TELEGRAM_BOT_TOKEN` lazımdır (@BotFather-dən alınır).
Token olmadan `voice.bot` işə düşmür və nə etmək lazım olduğunu yazır.

```bash
python -m voice.bot                                  # bot (long polling)
python tools/voice_check.py qeyd.ogg                 # bir səs faylını yoxla
python tools/voice_check.py --text "düyü neçəyədir"  # səsi keç, təhlili yoxla
```

| Qərar | Səbəb |
|---|---|
| `faster-whisper`, rəsmi `openai-whisper` yox | rəsmi paket ~2.5 GB PyTorch **və** sistemdə ffmpeg istəyir; bu maşında ffmpeg yoxdur. faster-whisper audio-nu PyAV ilə özü açır |
| Əvvəlcə regex, sonra LLM | ölçülüb: LLM təhlili 10-35 san əlavə edir. Şablon əmrlər onsuz da regex ilə tanınır |
| `language="az"` sabitlənib | dili özü seçəndə qısa mesajda türk/rus götürür və nəticə korlanır |
| `beam_size=1`, `vad_filter=True` | CPU-da 3-4 dəfə sürət; qısa əmrdə dəqiqliyə təsiri yoxdur |
| Telegram üçün adi `requests` | bota cəmi 3 metod lazımdır (getUpdates, getFile, sendMessage); çərçivə əlavə asılılıq və öyrənmə yükü gətirərdi |
| Long polling, webhook yox | webhook internetdən əlçatan HTTPS ünvan tələb edir |
| Transkript **həmişə** göstərilir | Whisper səhv oxusa, istifadəçi səbəbi dərhal görür |
| Ölçü sözü yoxdursa miqdar = 1 | "coca cola 2"-dəki rəqəm miqdar deyil; səhv miqdar səbətə səssizcə düşür |

**Ölçmələr** (i5-8265U, GPU yox, `small` model):

| Əməliyyat | Vaxt |
|---|---|
| Modelin ilk yüklənməsi | ~33 san (bir dəfə) |
| 3.4 san səs → mətn | ~11 san |
| 2.7 san səs → mətn | ~6.7 san |
| LLM ehtiyat təhlili | 10-35 san |

`VOICE_LLM_FALLBACK=false` qoysan yalnız şablon əmrlər işləyəcək, amma cavab
dərhal gələcək.

**Dəqiqlik hələ real səslə yoxlanmayıb.** Sınaq üçün Windows-un TTS səsi
işlədildi, o isə ingilis dilindədir və Azərbaycan sözlərini yanlış tələffüz
edir ("səbətim harada ucuzdur" → «Sabədim Harada Oqizdər»). Boru xətti tam
işləyir; modelin real Azərbaycan nitqindəki dəqiqliyini `tools/voice_check.py`
ilə öz səsinlə yoxlamaq lazımdır.

## Frontend: istifadəçi paneli vs. admin paneli

Səhifə **iki panelə** bölünüb (`app/static/nav.js`) və defolt açıq olan
istifadəçi panelidir:

| İstifadəçi paneli | Admin / Developer paneli |
|---|---|
| səbət, cavab (hero), məhsul müqayisəsi; **açılan panellər:** AI tövsiyəsi, qiymət tarixçəsi, endirim yoxlaması, profil | **baza sayğacları**, sistem statusu, mənbədən çəkmə, kataloq yükləmə, OCR/PSM ayarları, çıxarış və uyğunlaşdırma, kataloq siyahısı |

Səbəb: `robots.txt`, PSM rejimi, Ollama base URL və model adı **məhsulun içidir,
cavabı deyil**. Alış-veriş edən adam onları görməməlidir — amma developer üçün
onlar bir klik uzaqdadır (`#admin`).

**Hər iki panel DOM-dadır**, yalnız biri `display:none`-dur. Panel DOM-da
olmasaydı, digər skriptlərin `getElementById(...).addEventListener(...)`
sətirləri `null`-a düşüb faylı qırardı.

### Dizayn dili: Apple (apple.com) + trolley quruluşu

**v3-də palitra tam dəyişdi** (istifadəçinin açıq qərarı): vizual dil
**apple.com**-dan gəlir, səhifə QURULUŞU isə trolley.co.uk-dan qalır — kart
şəbəkəsi, «harada al» sətirləri, axtarış üstdə. Yalnız işıqlı rejim.

**YAŞIL TAMAMİLƏ ÇIXARILDI** — loqo, düymələr, başlıqlar, nişanlar, «ən ucuz»
siqnalı, hətta favikon. Yeganə vurğu Apple mavisidir; qalan rəng yalnız
**məzmundan** gəlir (market loqoları öz brend rənglərini saxlayır).

| Token | Dəyər | Məna |
|---|---|---|
| `--accent` | `#0071e3` | brend, naviqasiya, əsas hərəkət |
| `--accent-hover` | `#0077ed` | düymə hover |
| `--link` | `#0066cc` | mətn içindəki keçid |
| `--cheapest` | `#0071e3` | **ən ucuz qiymət** |
| `--ok` | `#0066cc` | təsdiqlənib |
| `--info` | `#6e6e73` | yoxlaya bilmirik |
| `--danger` | `#d70015` | bahalı / şübhəli / xəta |
| `--ai` | `#8944ab` | **yalnız AI** |

**Şrift şəbəkədən yüklənmir.** Poppins linki silindi: SF ailəsi
(`-apple-system` → `BlinkMacSystemFont` → `SF Pro`) əməliyyat sistemindədir,
olmayan yerdə `Helvetica Neue` → `Arial` zəncirinə düşür. Nəticə: iki xarici
sorğu az, şrift sıçraması yox.

**Şkalalar:** radius — düymə `980px`, kart `18px`, input `12px`, nişan `8px`;
boşluq — **8px** şəbəkəsi (trolley-in 5px-i əvəzinə); kölgə — `0 4px 16px
rgba(0,0,0,.06)`, hover `0 8px 24px rgba(0,0,0,.10)`.

**Kontrast ÖLÇÜLDÜ, gözlə qiymətləndirilmədi** (ağ fonda):

| Token | Ölçmə | Qərar |
|---|---|---|
| `--text #1d1d1f` | **16.83:1** | ✓ |
| `--text-secondary #6e6e73` | **5.07:1** | ✓ — kiçik etiketlər buradan gəlir |
| `--text-tertiary #86868b` | **3.62:1** | AA-dan KEÇMİR → yalnız placeholder, tire, üstüxətli köhnə qiymət |
| `--accent #0071e3` mətn kimi | **4.70:1** | ✓ |
| **ağ** mətn `--accent` fonda | **4.70:1** | ✓ — düymə mətni ağ qala bilir |
| Apple qırmızısı `#ff3b30` | **3.55:1** | zəif → tünd variant `#d70015` (5.38:1) |

**«Ən ucuz» yenə YALNIZ rənglə verilmir.** İndi o, brendlə eyni mavidir, ona
görə siqnal formaya söykənir: neytral fon + `--cheapest` çərçivə + ✓ nişanı +
ekran oxuyucusu üçün gizli mətn. `test_ən_ucuz_siqnalı_yalnız_rənglə_verilmir`
bunu kilidləyir — kimsə dolu mavi fon qaytarsa, qapı sınır.

**Səth ierarxiyası (Apple ritmi):** səhifə ağdır, **bölmə** boz altlıqdır
(`--bg-subtle #f5f5f7`, çərçivəsiz), bölmənin **içindəki kartlar** ağdır.
Əvvəlki keçiddə hər ikisi ağ idi və nazik çərçivələr üst-üstə düşürdü.

**Üst panel** yarımşəffafdır: `backdrop-filter: saturate(180%) blur(20px)`.
`saturate(180%)` altdakı rəngli məzmunun blur zamanı solmasının qarşısını alır —
Apple məhz bu dəyəri işlədir. Blur dəstəklənməyən brauzerdə `@supports` bloku
fonu tam ağ saxlayır.

**Segmented control** (İstifadəçi / Admin) Apple-ın öz idarəsi kimi qurulub:
yol boz, seçilmiş seqment **ağ** və yüngül kölgə ilə qalxır. Əvvəl seçilmiş
seqment doldurulmuş yaşıl idi — düymə kimi görünürdü, halbuki bu, rejim
keçididir, hərəkət deyil.

**Kiçik CAPS etiketlər silindi** (`MARKET`, `MÖVCUDDUR`, `MAKSİMUM QİYMƏT`).
CAPS + geniş hərf aralığı dashboard dilidir; SF-də oxunuşu pisləşdirir. İndi
adi yazılış, 13px, çəki 500.

### Üç dil: AZ · EN · RU

Üst paneldə dil keçidi var; seçim `localStorage`-də saxlanılır və bütün
səhifələrə şamil olunur. **271 açar**, hər biri üç dildə.

**Niyə brauzerdə, serverdə yox?** Səhifələr statikdir və server şablon motoru
işlətmir. Dili brauzerdə dəyişmək o deməkdir ki, seçim **anidir** — səhifə
yenidən yüklənmir, sorğu getmir, backend dəyişmir.

**Azərbaycanca mətn HTML-in içində qalır.** Hər elementdə həm `data-i18n`
açarı, həm də azərbaycanca mətnin özü var. JS işləməsə (yükləmə xətası, köhnə
brauzer) səhifə boş qalmır — azərbaycanca oxunur. Tərcümə qatı yalnız üstünə
yazır.

**Dinamik mətn:** `app.js`, `deals.js` və s. `t("açar")` çağırır. Dil dəyişəndə
`basketiq:lang` hadisəsi atılır və hər modul **öz** blokunu yenidən çəkir.

**İkonlu düymələr:** `data-i18n` elementin bütün məzmununu əvəz edir — ikonlu
düymədə birbaşa işlətsək ikon silinərdi. Orada yalnız mətn `<span>` ilə sarılır.

**Kateqoriyalar bazada azərbaycanca qalır** (filtr ünvanı və API sorğusu ondan
asılıdır), tərcümə yalnız ekrandadır: `t("cat." + ad, ad)` — lüğətdə açar
yoxdursa azərbaycanca adı görünür, açarın özü yox.

**Üç test kilidləyir:** hər açarın üç dildə olması, HTML-də və JS-də çağırılan
hər açarın lüğətdə mövcudluğu, dil keçidinin hər səhifədə olması. Mutasiya ilə
yoxlanılıb: bir dili silmək və ya yanlış açar yazmaq testi düşürür.

**Tərcümə olunmayan hissə:** backend-in QURDUĞU cümlələr — AI qeydi, endirim
yoxlamasının səbəb mətnləri, profil planının qeydləri və mənbə təsvirləri.
Onlar rəqəmlərlə birlikdə serverdə yığılır; tərcümə üçün API-nin açar+parametr
qaytarması lazımdır. Məhsul və market adları da tərcümə olunmur — onlar datadır.

### Toxunma hədəfləri: 44px (Apple HIG)

Apple HIG interaktiv element üçün **44×44** tappable sahə tövsiyə edir — bu,
GÖRÜNTÜ deyil, HƏDƏF ölçüsüdür. Ona görə iki yanaşma işlədilir:

| Element | Görünən | Toxunma | Necə |
|---|---|---|---|
| `.btn`, `.btn-ghost` | 44px | 44px | `min-height` — düymənin özü |
| `.segmented` yolu | 44px | 44px | seqment 40 + 2×2 daxili boşluq |
| `.icon-btn` | 36×36 | **44×44** | görünməyən `::before` örtüyü |
| `.basket-chip-del` | 24×24 | **44×44** | görünməyən `::before` örtüyü |
| `.check`, `.filter-opt` | — | 44px sətir | `min-height` (hədəf `<label>`-dir) |
| `input`, `select` | 44px | 44px | `min-height` — düymə ilə eyni sətirdə dayanır |

**Niyə bəzi yerdə örtük, bəzi yerdə həqiqi ölçü?** Cədvəl sətrindəki və üst
paneldəki dairəvi ikon düyməsini 44px etsək sətirlər və panel ağırlaşır; orada
hədəf `::before` ilə genişlənir, görüntü kiçik qalır. Düymələr isə onsuz da
mətn daşıyır — onların 44px olması səhifəni ağırlaşdırmır, əksinə Apple
ritminə salır.

**Örtük qonşunu udmur:** ölçüldü — «Sətirlər» ilə «sil» arasındakı ara 16px,
örtük hər tərəfə 4px uzanır. Brauzerdə təsdiqləndi: «Sətirlər» həm
mərkəzindən, həm sağ kənarından kliklənir.

**`svg`-yə `pointer-events: none`** verilir ki, hadisənin hədəfi həmişə
düymənin özü olsun — `<use>` elementi hədəfə çevriləndə klik zənciri
gözlənilməz davranır (ölçülüb).

### Silmə təsdiqi: iki addım, `confirm()` YOX

Admin panelində «sil» düyməsi **təsdiqsiz** idi — bir klik kataloqu, onun bütün
qiymətlərini və yetim qalan məhsulları geri dönməz silirdi. Canlı yoxlama
zamanı göründü.

İndi düymə **iki addımlıdır**: birinci klik onu «Silinsin?» vəziyyətinə keçirir
(qırmızı pill), ikinci klik silir. 5 saniyə toxunulmasa öz halına qayıdır;
**Escape** və başqa yerə klik də ləğv edir.

**Niyə native `confirm()` deyil?** Üç səbəb: (1) səhifəni **bloklayır** —
brauzer avtomatlaşdırması, o cümlədən bizim öz Selenium yoxlamalarımız, dialoq
açılan kimi cavab verməyi dayandırır; (2) üslublandırmaq mümkün deyil — Apple
dizayn dilinin ortasında əməliyyat sisteminin boz qutusu açılır; (3) düymələri
ingiliscə gəlir («OK / Cancel»), halbuki interfeys tam azərbaycancadır.
`test_silmə_təsdiqi_native_confirm_işlətmir` bunu kilidləyir.

Rəng **tək siqnal deyil**: düymənin öz mətni («Silinsin?») nə baş verəcəyini
deyir, yəni rəngi görməyən istifadəçi də başa düşür.

**Üç silmə düyməsinin hamısı eyni mexanikadan keçir** — kataloq, səbət çipi və
müqayisə cədvəlindəki sətir. Mexanika `armDeleteButton(btn, onConfirm)`
funksiyasındadır: o, yalnız təsdiqi bilir, silmənin ÖZÜ çağıran tərəfdə qalır.
`test_hər_silmə_sorğusu_təsdiqin_arxasındadır` hər `DELETE` sorğusundan geriyə
gedib qeydiyyat nöqtəsini yoxlayır — birbaşa `addEventListener("click")`
qalsa, qapı sınır.

**Market rəng nöqtələri** kimlik bildirir, status yox — ona görə palitrada
brend yaşılı, `#4caf50` və `#cc3327` **yoxdur**. Rəng market ADINDAN hesablanır
(`app/static/store-colors.js` — hash xananı təklif edir, toqquşma əlifba
sırasında xətti sınaqla həll olunur); sıra indeksinə bağlasaydıq, marketlərin
sırası dəyişəndə rənglər də dəyişərdi.

**Ən böyük element səhifədə təkdir:** səbətin cavabı (`.hero-price`, 56px).
Market adı 24px, səhifə başlığı 30px, admin panelindəki stat rəqəmləri 36px —
yəni istifadəçi ilk baxışda cavabı görür. Bu iyerarxiyanı
`test_verdict_səhifənin_ən_böyük_elementidir` qoruyur.

**Hər ekranda bir primary düymə:** istifadəçi panelində «Tövsiyə al», admin
panelində «Mənbədən çək».

### İlk ekran: bir sual, bir cavab

v2-yə qədər səhifə **4918px** uzunluğunda idi və yuxarıda dörd stat kartı
(MARKET / KATALOQ / MƏHSUL / QİYMƏT) dururdu. Onlar istifadəçinin sualına
(«səbətim harada ucuzdur?») cavab vermirdi, sadəcə datanın nə qədər kiçik
olduğunu reklam edirdi — ona görə **admin panelinə köçürüldü**.

İndi skroll etmədən görünən hissədə **üç element** var:

1. **Səbət** — ad + miqdar + sil çipləri (cədvəl aşağıda qalır).
2. **Cavab** — səhifənin ən böyük rəqəmi.
3. **Bir sətir izah** — «Araz ilə müqayisədə 2.40 ₼ ucuz».

Bölünmüş alış (bir neçə marketi gəzmək) **böyük rəqəm kimi göstərilmir** —
cavabın altında ayrıca sətir kimi təklif olunur. Səbəb: ən böyük rəqəm
şərtsiz cavab olmalıdır; əvvəl o, dərhal iki şərtlə məhdudlaşdırılırdı
(«3 marketi gəzsəniz», «tək marketlə olmur»).

**Hazırkı data ilə şərtsiz cavab yoxdur.** Heç bir market səbətin hamısını
satmır, ona görə ekranda yenə şərtli rəqəm görünür — «natamam market qalib
elan edilmir» qaydası dəyişmir. Kod hər iki halı dəstəkləyir: tam səbəti satan
market yarananda ilk ekran avtomatik «market adı + cəm» formasına keçir.

Tarixçə, endirim yoxlaması, AI tövsiyəsi və profil **defolt bağlıdır**
(`<details>`, JS akkordeon yox — klaviatura, ekran oxuyucusu və `Ctrl+F`
onsuz da işləyir). Nəticə: səhifə **4918px → 1831px** (−63%).

Alt hissədə görünən dürüstlük qeydi var: qiymətlərin **həftəlik kataloqdan**
gəldiyi və filialda fərqlənə biləcəyi yazılır.

### Endirim yoxlaması: exception-first

Bu bölmə tətbiqin **ən güclü fərqləndirici funksiyasıdır** — kataloq «köhnə
qiymət» iddiası edir, biz onu öz müşahidələrimizlə tutuşduruq. Ona görə vizual
diqqətin ən çoxunu o alır və siyahı **diqqət tələb edən sətirlərlə başlayır**:

```
şübhəli  →  təsdiqlənməyib  →  endirim yoxdur  →  təsdiqlənib
```

Hər sətir: solda status pill, ortada məhsul + səbəb, sağda tabular qiymət.
Sol kənarda 3px rəngli zolaq siyahını sürətlə skan etməyə imkan verir.

İki səssiz risk testlə kilidlənib: backend-dəki `VERDICTS` ilə frontend
xəritəsinin **tam** üst-üstə düşməsi, və `rank` sırasının pozulmaması. İkisi də
sınsa səhifə yenə «işləyər» — sadəcə ən vacib sətirlər aşağı düşər və statuslar
neytral boz görünər.

### İkon sistemi: market və məhsul vizual entity kimi

Marketlər və məhsullar düz mətn deyil, **ikon + ad** qrupu kimi göstərilir
(`.entity` + `.avatar`). Hər ikisi eyni naxışdan istifadə edir — yalnız ölçü
fərqlidir.

| Nə | İkon haradan gəlir |
|---|---|
| Market | **Rəngli dairə + adın ilk hərfi.** `stores` cədvəlində yalnız `slug`/`name`/`website` var — **real loqo yoxdur**, ona görə saxta loqo çəkilmir. Əvvəl hamısına eyni boz mağaza ikonu verilirdi, yəni nişan heç nə ayırd etmirdi |
| Məhsul | `products.category` sahəsindən: «süd məhsulları» → şüşə, «yağ və souslar» → yağ qabı, «içkilər» → butulka… |

Məhsul **şəkli** də yoxdur: nə DB-də sütun var, nə kataloqdan çıxarılır.
Uydurma şəkil qoymaq istifadəçini yanıldardı, ona görə kateqoriya ikonu
işlədilir — o, ən azı doğru məlumat verir.

`category` sahəsi **yeni data deyil** — `products` cədvəlində onsuz da var idi,
sadəcə `/api/basket/compare` cavabına daxil edilməmişdi.

**Səssiz sınma riski və onun testi.** `CATEGORIES` siyahısına yeni kateqoriya
əlavə olunsa, frontend onu xəritədə tapmır və hamısına eyni «paket» ikonu
verir — səhifə işləyir, heç bir xəta yoxdur, sadəcə ikonlar mənasını itirir.
`tests/test_ui_contract.py` bunu tutur: siyahı ilə xəritənin **tam** üst-üstə
düşdüyünü, hər ikonun SVG kitabxanasında mövcudluğunu və hər JS selektorunun
HTML-də olduğunu yoxlayır.

### AI mətnində vurğulama

Tövsiyə mətnində məbləğlər və qalib marketin adı `<mark>` ilə işıqlanır.
İki incə detal var:

- **Valyuta vahidi məcburidir** (`19.65 AZN`, `2,45 ₼`). Olmasaydı «2.5%»
  yağlılıq və «1.8 L» həcm də vurğulanardı — onlar isə məbləğ deyil.
- **`` işləmir.** Azərbaycan şəkilçisi ada yapışır: `Araz` nə «Arazda»,
  nə «Araz-a» tutur. Onun əvəzinə «hərf olmayan simvol» sərhədi işlədilir —
  «Arazda» sözündə yalnız «Araz» işıqlanır, şəkilçi vurğudan kənarda qalır.

Mətn modeldən gəldiyi üçün əvvəlcə tam `escapeHtml`-dən keçir, `<mark>`
etiketləri **sonra** əlavə olunur — modelin yazdığı `<script>` sadəcə mətn
kimi qalır.

### Dizayn qərarları

| Qərar | Səbəb |
|---|---|
| Bütün rənglər `:root` token-lərindən və `color-mix()` törəmələrindən | brend rəngini dəyişmək bir sətirdir; qrafik sütunları da ardınca gəlir |
| Qrafik rəngləri CSS-dən **oxunur** (`getComputedStyle`) | canvas CSS dəyişənlərini bilmir; hardcode etsək səhifə bir rəngdə, qrafik başqa rəngdə qalardı |
| Dark mode **yoxdur** (`color-scheme: light`) | qiymət siqnalları iki fonda eyni oxunmur; trolley sistemi də yalnız işıqlıdır |
| Hover-də yalnız **interaktiv** kartlar qalxır | əvvəl hər kart qalxırdı — kursor gəzdikcə səhifə "titrəyirdi" |
| Ən ucuz xana: **çərçivə + ✓ + `sr-only` mətn** (dolu fon YOX) | brend rəngi yaşıl olduğu üçün dolu yaşıl fon «brend» ilə «ucuz» siqnalını qarışdırardı; rəng onsuz da tək siqnal olmamalıdır |
| Natamam marketin sütunu **zolaqlıdır** | onun cəmi kiçikdir (çatışmayan məhsul 0 sayılır), yəni sütunu qısa — "ucuz" görünür; zolaq və "6/7 məhsul" yazısı bu tələni gözlə görünən edir |
| Qənaət yoxdursa **uydurulmur** | backend `savings`-i yalnız iki TAM səbət olanda hesablayır; əks halda səbəb yazılır |

---

## Kataloq ekranları: marketlər, endirimlər, məhsul səhifəsi

Trolley.co.uk-un üç ekranı BasketIQ-in dörd marketinə uyğunlaşdırılıb.
Marketlərin **yeganə reyestri** `app/stores.py`-dır:

| Market | slug | Data |
|---|---|---|
| Araz Market | `araz` | var (kataloqdan) |
| Bravo Market | `bravo` | var (kataloqdan) |
| Bazar Store | `bazar-store` | **hələ yox** → «Tezliklə» |
| Rahat Market | `rahat` | **hələ yox** → «Tezliklə» |

Bazadakı `stores` cədvəli bundan genişdir: orada test marketləri və köhnə
mənbələr də qala bilər. Reyestrdən kənar market **istifadəçi panelinin heç bir
yerində görünmür** — istifadəçiyə vəd olunmayan market göstərmək məlumat
deyil, səs-küydür.

### Süzgəc bütün istifadəçi ekranlarına şamildir

Əvvəlcə süzgəc yalnız yeni ekranlara qoyulmuşdu və nəticə ekranda göründü:
market şəbəkəsi dörd market göstərirdi, **səbət cavabı isə «ən çox əhatə:
OBA» yazırdı**. İstifadəçi ana səhifədə olmayan, ona vəd edilməyən markete
yönləndirilirdi — və heç bir test bunu tutmurdu, çünki hər iki tərəf
ayrılıqda «işləyirdi».

Ona görə süzgəc bir yerdən — `app/stores.py`-dəki `store_filter()` və
`display_names()` funksiyalarından — gəlir və bu hesablamaların hamısına
tətbiq olunur:

| Modul | Nə süzülür |
|---|---|
| `app/api/basket.py` | səbət müqayisəsi, market cəmləri, «ən ucuz» |
| `app/analytics.py` | qiymət tarixçəsi, qrafik siyahısı, endirim yoxlaması, «qonşuda ucuzdur» |
| `app/recommend.py` | alternativ qablaşdırma təklifi |
| `app/catalog.py` | endirimlər, «harada al», variantlar |

**Admin panelinə toxunulmur:** kataloq siyahısı, mənbə çəkmə və baza
sayğacları bazanın bütün tarixçəsini göstərməkdə haqlıdır — onlar məhsulun
içidir, cavabı deyil.

**Ad da reyestrdən gəlir.** Bazada market «Araz» yazılıb, məhsul isə «Araz
Market» adlanır. İki ad iki problem yaradır: istifadəçi eyni marketi iki cür
görür, üstəlik market rəngi ADDAN hesablandığı üçün (`store-colors.js`) eyni
market cədvəldə bir, qrafikdə başqa rəngə düşür.

Süzgəcin görünən nəticəsi: yalnız kənar marketdə satılan məhsullar
UI-dan çıxdı. Bu, itki deyil —
**dürüstlükdür**: həmin qiymətlər bizim dörd marketimizdən gəlmirdi.

### 1. Market şəbəkəsi (`store-grid.js`)

Ana səhifənin başında dörd kart: düz künclü, ağ fonlu, nazik boz kənarlı,
mərkəzdə loqo. Radius şkalasından kənara çıxan yeganə yer buradır və
qəsdəndir — trolley-nin mağaza şəbəkəsində loqo kvadrat çərçivədə dayanır.

Loqolar `app/static/images/`-dədir (`araz.png`, `bravo.png`, `bazar.png`,
`rahat.png`). **Fayl yoxdursa səhifə sınmır:** `error` hadisəsi şəkli silir və
yerinə marketin adı yazılır. Uydurma loqo çəkilmir.

Kart marketin öz səhifəsinə aparır (`/store/<slug>`). Datası olmayan marketin
səhifəsi də **açılır** — boş siyahı əvəzinə vəziyyəti izah edir. Kartı
kliklənməz etmək səbəbi gizlədərdi.

### 2. Bugünün ən sərfəli endirimləri (`deals.js`)

Hər məhsul üçün **bir** kart və **ən böyük** faiz endirim. Eyni məhsul iki
marketdə endirimdədirsə, kiçik faiz kartın içindəki müqayisədə qalır.

İki süzgəc var (`app/catalog.py`):

| Hədd | Dəyər | Səbəb |
|---|---|---|
| `MAX_DEPTH` | 70% | ərzaqda daha dərin endirim praktiki olaraq olmur — ya OCR səhvi, ya uydurma köhnə qiymət. Sıralama məhz faizə görə olduğu üçün süzgəcsiz siyahının **başında** həmişə zibil dayanardı |
| `MIN_DISCOUNT_PCT` | 3% | 1-2% dəyişmə istifadəçinin qərarını dəyişmir |

Hər kartın altında həmin məhsulun **digər marketlərdəki** qiyməti var: 50%
endirim qonşunun endirimsiz qiymətindən baha ola bilər. Məhsul tək marketdədirsə,
boş sətir yox, açıq cümlə yazılır — «Yalnız Araz Market-də tapılıb».

### 3. Məhsul səhifəsi (`/product/<id>`)

**«Harada al» sütun üzərində yox, SƏTİR üzərində qurulub.** Trolley-də dörd
market dörd sütundur, çünki onların tam kataloqu var. Bizdə yoxdur: məhsulun
qiyməti hansı marketlərdə varsa, o qədər sətir olur. Boş xana, `0.00` və ya
xəta **heç bir halda** görünmür; hansı marketin datasının hazır olmadığı isə
cədvəlin altında bir sətirlə yazılır.

**«Ən ucuz» ilə «ən sərfəli» eyni şey deyil:**

```
125 ml  → 1.39 ₼   (ən ucuz — cibdən çıxan pul)
1000 ml → 4.55 ₼   (ən sərfəli — 1 L = 4.55 ₼, kiçikdə isə 11.12 ₼)
```

Bir məhsulun bütün təklifləri **eyni ölçüdədir**, yəni vahid qiyməti
sıralaması qiymət sıralaması ilə üst-üstə düşür. Ona görə «ən sərfəli» nişanı
təkliflər cədvəlində yalnız «ən ucuz»dan **fərqlənəndə** verilir — əks halda
iki nişan həmişə bir sətirdə dayanıb heç nə əlavə etməzdi.

Səhifədə ayrıca «Oxşar məhsullar» (eyni kateqoriya) və «Eyni brenddən»
bölmələri var. Hər ikisi yalnız **qiyməti olan** məhsulları göstərir: qiyməti
olmayan kart kliklənəndə boş səhifə açılardı.

### 4. «Rəylər» əvəzinə AI qeydi (`ai/product_note.py`)

Trolley-də məhsulun altında müştəri rəyləri var. **Bizdə rəy yoxdur** — nə
istifadəçi hesabı, nə rəy cədvəli, nə də bir dənə real müştəri. Modelə «rəy
yaz» demək saxta rəy istehsal etmək deməkdir.

Ona görə bölmənin adı da, prompt-u da dəyişdirilib: model yalnız **hesablanmış
qiymət faktlarını** cümləyə çevirir. Üç qat qoruyucu var və prompt onlardan
yalnız biridir:

1. **fakt bloku** — bütün rəqəmlər Python-da hesablanır, modelə hazır verilir;
2. **rəqəm yoxlaması** — cavabdakı hər onluq ədəd fakt blokunda axtarılır
   (`ai.advisor.verify_numbers`);
3. **rəy sözləri süzgəci** — «dadlı», «tövsiyə edir», «alıcılar» tipli ifadə
   görünsə cavab atılır.

Üçündən biri düşəndə nəticə eynidir: bölmə **göstərilmir**. Boş kart və ya
xəta mesajı çıxmır, səhifənin qalanı isə modeldən asılı deyil.

Real Claude cavabı (ölçülüb, 3 rəqəmin hamısı təsdiqlənib):

> Bu dondurma yalnız Araz Marketdə 4.55 AZN-ə var, ona görə müqayisə üçün
> ikinci qiymət yoxdur. 125 ml variantı 1.39 AZN-ə daha ucuz görünsə də, litr
> hesabı 11.12 AZN-dir, 1000 ml-lik qablaşdırma isə litri 4.55 AZN ilə daha
> sərfəlidir.

Qeyd **keşlənir** (`ai/cache.py`), keş açarı isə fakt blokunun özüdür: qiymət
dəyişəndə qeyd avtomatik yenidən yazılır.

### 5. Məhsul şəkilləri: kataloqdan kəsilir, saytdan endirilmir

Trolley şəkilləri marketin öz onlayn mağazasından götürür. **Bizdə belə mənbə
yoxdur** — ölçülüb (`logs/sources.md`): Araz-ın data ünvanlarını `robots.txt`
qadağan edir, Bravo-nun kataloq səhifəsi «0 məhsul» qaytarır, Bazar Store-un
saytı baxımdadır.

Amma şəkil əlimizdədir — sadəcə kataloq səhifəsinin **içindədir**.
`ingestion/layout.py` onsuz da hər məhsulun qiymət qutusunu tapır; kataloq
kartlar şəbəkəsi olduğu üçün iki qonşu qiymət qutusu arasındakı məsafə xananın
ölçüsünü verir. Şəkil qiymətin üstündədir:

```
xana = qiymət qutusunun mərkəzi
       yuxarı  → bir sıra addımı
       yanlara → yarım sütun addımı
```

**Məhsulu şəklə nə bağlayır?** `prices.raw_line` — kartın OCR-dan çıxan orijinal
sətri. O sütun şəffaflıq üçün yazılırdı, indi işə yaradı: səhifə yenidən analiz
olunur və kartların sətirləri `raw_line` ilə tutuşdurulur (`difflib`).

**Yalnız mətn oxşarlığı səhvə apardı** — düşbərənin yerinə su qabı düşdü.
Namizədləri **qiymət** daraldır, hədd `MATCH_THRESHOLD = 0.55`, iki namizəd
bir-birinə yaxın olanda şəkil **verilmir**. Səbəb sadədir: səhv şəkil
placeholder-dən pisdir — istifadəçi başqa məhsulu görüb qiyməti ona aid sayır.

Boş kadr (tək rəngli sahə) atılır, şəkli tapılmayan məhsul neytral
placeholder alır (`/static/images/product-placeholder.svg`). **Uydurma məhsul
şəkli çəkilmir.**

**Kadrın eni: alt hədd lazım oldu.** Kadr sütun addımından hesablanır, addım isə
qonşu qiymət qutuları arasındakı median məsafədir. Kartlar dəqiq şəbəkədə
dayanmadığı üçün qonşu SIRALARIN qutuları da x oxunda yan-yana düşür və median
kiçilir. Ölçüldü (20 səhifə): qutu eni sabit ~144 px, addım isə 112-414 arasında
oynayır — **altı səhifədə qutunun özündən kiçik**. Nəticə: kadr kartın solunu
kəsirdi və brend adı itirdi («Flomaster» → «omaster», «Heineken» → «ineken»),
bəzi kadrlarda isə yalnız qiymət qutusu qalırdı.

`MIN_COL_RATIO = 2.2` alt həddi qoyuldu. **2.2 harada ölçülüb:** addımın doğru
hesablandığı səhifələrdə onun qutu eninə nisbəti 2.08-2.87-dir; 2.2 həmin
aralığın aşağı ucudur, yəni alt hədd yalnız absurd kiçik dəyəri qaldırır.
Sıra addımına toxunulmadı — o, heç bir səhifədə qutu hündürlüyünə yaxınlaşmır.

**Sınanan və atılan variant:** mərkəzləri klasterləyib addımı ordan götürmək —
ölçüldü, 20 səhifədən 13-də yenə qutunun ikiqatından kiçik çıxır.

**Ölçülmüş əhatə (2026-09-09):** 188 məhsuldan **61-inin** şəkli var (≈32%),
hamısı Araz kataloqlarından. Şəkil yalnız ilk 20 səhifədən kəsilir
(`build_images`), məhsullar isə 54 səhifənin hamısından gəlir — fərq buradandır. Bravo-nun 8 məhsulunda şəkil **yoxdur** — o data
kataloq səhifəsindən gəlmir, deməli kəsiləcək kadr da yoxdur.

Şəkillər generasiya olunur, ona görə repo-ya düşmür (`.gitignore`). Təmiz
klonda hamısı placeholder görünür; bərpa: `python tools/build_images.py`.

**Yoxlandı, düzəldildi, yenidən yoxlandı (2026-09-09).** 73 şəklin hamısına
gözlə baxıldı: **21-i (29%) səhv məhsulu göstərirdi** — «sosis» üçün Pringles,
«it yemi» üçün plastilin, «paltar yuyucu vasitə» üçün Tuc krekeri. Səbəb hədd
deyildi, iki kod qüsuru idi:

1. **Uyğunlaşma bir-çoxa idi.** Seçilmiş kart siyahıdan çıxarılmırdı, ona görə
   iki məhsul eyni kartı «qazanırdı» — 73 fayldan yalnız 63-ü unikal idi.
   İndi kart da, məhsul da yalnız bir dəfə seçilir və qərar bazadakı sıra ilə
   deyil, **xal sırası** ilə verilir.
2. **Qiymət açarı ehtiyac anında sönürdü.** `pool = priced or cards` — qiyməti
   uyğun kart tapılmayanda süzgəc tamamilə düşür və qərarı yalnız mətn verirdi.
   İndi qiymət **məcburidir**: uyğunluq yoxdursa məhsul placeholder alır.

Nəticə eyni metodla yenidən sayıldı:

| | Başlanğıc | Uyğunlaşma | + layout | + yenidən emal | + atribut |
|---|---|---|---|---|---|
| Şəkil | 73 | 62 | 51 | 60 | **61** |
| Doğru | 48 (66%) | 48 (77%) | 42 (82%) | 50 (83%) | **52 (85%)** |
| Səhv | **21 (29%)** | 10 (16%) | 6 (12%) | 6 (10%) | **6 (10%)** |
| Unikal kadr | 63/73 | 62/62 | 51/51 | 60/60 | **61/61** |

Üçüncü addımdan sonra `raw_line` köhnə qalmışdı, ona görə dördüncü addımda
**kataloq bütöv yenidən emal olundu** (54 səhifə OCR → LLM → baza). Nəticə:
kartlar öz məhsullarını tapdı — «ASH Su qabı» kartı artıq «karandaş»a yox,
**su qabı** məhsuluna düşür.

**Qalan 6 səhv artıq şəkil səhvi deyil:** kart doğru tapılır, LLM isə həmin
sətirdən yanlış ad çıxarır (kart «Süfrə Sous» deyir, bazadakı ad «duz»). Növbəti
addım atribut çıxarmadadır. Təfərrüat: `logs/image-check.md`.

### 6. Axtarış səhifəsi (`/search`)

Şəkilli kart şəbəkəsi + üç filtr: market, kateqoriya, maksimum qiymət.

**Filtr vəziyyəti ÜNVANDADIR, JS dəyişənində yox:**

```
/search?q=süd&market=araz&category=içkilər&max_price=5
```

Yəni nəticə paylaşıla və brauzerin «geri» düyməsi ilə gəzilə bilər. Vəziyyət
yalnız yaddaşda qalsaydı, istifadəçi filtri seçib linki göndərəndə qarşı tərəf
başqa səhifə görərdi.

**Filtr menyusu real datadan qurulur** (`facets`) — boş kateqoriya menyuda
görünmür. Seçilə bilən, amma heç bir nəticə verməyən filtr istifadəçini
aldadır.

### Ana səhifə trolley strukturuna keçdi

Axtarış paneli **yuxarıya** qalxdı, market şəbəkəsi onun altındadır. Endirimlər
artıq kart şəbəkəsi deyil — trolley-dəki kimi **nömrələnmiş siyahıdır**:
şəkil + ad + ölçü + marketlərin qiymətləri yan-yana. Səbət bloku aşağı köçdü.

**Alış-veriş yoxdur:** nə «səbətə əlavə et» düyməsi, nə checkout, nə ödəniş.
Səbət burada alış siyahısıdır, sifariş deyil — məqsəd qiyməti göstərməkdir.

### İkon kitabxanası bir faylda

Üç səhifə eyni 30 ikonu işlədir. Sprite HTML-in içində qalsaydı, üç nüsxə
yaranardı — biri yenilənib digəri köhnə qalardı və səhifə yenə «işləyərdi»,
sadəcə səhv ikon göstərərdi. Ona görə sprite `app/static/icons.svg`-dədir,
`icons.js` isə onu səhifəyə salır.

`<use href="icons.svg#icon-x">` variantı seçilmədi: xarici fayla birbaşa
istinad **Safari-də işləmir**. Fayl gec gəldiyi üçün mövcud `<use>`
istinadları əl ilə yenidən həll etdirilir (`href`-i silib eyni dəyərlə geri
yazmaq) — bu, hər brauzerdə eyni işləyir.

---

## Chain-of-thought filtri: xam model mətni brauzerə çatmır

Model bəzən cavabdan əvvəl öz-özü ilə danışır:

```
<think>Okay, let me work through this. Araz 19.65, Bravo 16.54...</think>
Araz marketini seçin, çünki...
```

Bu mətn istifadəçi üçün deyil. Ekranda görünsə üç problem yaranır: tövsiyə
qarışıq olur; model natamam düşüncəsini "fakt" kimi yazır; və rəqəm yoxlaması
düşüncədəki aralıq rəqəmləri sayıb **yalan xəbərdarlıq** verir.

Filtr `ai/sanitize.py`-dədir və `stream_advice()`-in içində işləyir — yəni
modelə çıxışın **yeganə qapısında**. Xam mətn bu funksiyadan kənara çıxmır.

**Niyə iki mexanizm var?** Cavab token-token axır, yəni `<think>` etiketi iki
parçaya bölünə bilər (`<thi` + `nk>`). Adi `re.sub()` bunu tuta bilməz.

| Mexanizm | Nə edir |
|---|---|
| `ReasoningFilter` | axın üçün vəziyyət maşını: etiketin yarısı gələndə ~12 simvol buferdə saxlanır, tam gələndə blokun sonuna qədər atılır |
| `strip_reasoning()` | axın bitəndən sonra tam mətn üzərində: `Reasoning:` sətir etiketləri və `Cavab:` son-cavab markeri |

Son təmiz mətn SSE-nin `done` hadisəsi ilə göndərilir və UI mətni onunla əvəz
edir. Adətən iki versiya eynidir və heç nə görünmür — ölçüldü:
`axın == son mətn: True`.

**Yalançı pozitivdən qorunma:** yalnız **blok strukturu** silinir. `"Bunun
reasoning hissəsi maraqlıdır"` toxunulmaz qalır, çünki marker sətrin əvvəlində
və ikinöqtə ilə tanınır. `"Qiymət < 20 AZN"` da qalır — `<` hər zaman etiket
demək deyil. Hər ikisi `tests/test_sanitize.py`-də kilidlənib (42 test, hər hal
1/3/7/tam parça ölçüləri ilə).

---

## LLM seçimi: Claude API + Ollama ehtiyat

```
LLM_PROVIDER=claude  ->  Claude API əsas, Ollama EHTİYAT
LLM_PROVIDER=ollama  ->  yalnız Ollama (defolt)
```

Claude qırılanda (açar bitib, limit aşılıb, internet yoxdur) sorğu **sükutla
Ollama-ya keçir** — dashboard işləməyə davam edir, sadəcə yavaş. Deployment üçün
vacibdir: xarici xidmətin dayanması bütün layihəni dayandırmamalıdır.

| Qərar | Səbəb |
|---|---|
| LangChain-in `with_fallbacks()` | zəncirlərdə (`chains.py`, `advisor.py`, `matcher.py`) **heç nə dəyişmir** — `.batch()` və `.astream()` eyni qalır |
| `langchain_anthropic`, birbaşa SDK yox | AI qatı LCEL zəncirləridir; `ChatAnthropic` içəridə elə rəsmi `anthropic` SDK-nı çağırır |
| Açar yoxdursa Claude ümumiyyətlə qurulmur | əks halda hər sorğu 401 alıb fallback-ə düşərdi — nəticə düzgün, amma hər çağırışa boş gecikmə |
| Keş açarı **aktiv** modelin adını daşıyır | əks halda Claude-un cavabı Ollama keşindən oxunardı |
| `effort=low` | çıxarış qısa JSON qaytarır — dərin düşünmə nə dəqiqlik qatır, nə lazımdır |

### Ölçülmüş fərq (eyni sətir, eyni prompt)

| | Claude (`claude-opus-5`, effort=low) | Ollama (`qwen3:4b`, GPU yoxdur) |
|---|---|---|
| Kataloq çıxarışı (1 sətir) | **1.7 san** | **64 san** |
| Məhsul uyğunlaşdırma | 2.1 san | — |
| Məsləhət (ilk söz / tam) | 2.9 san / 7.3 san | — |

Hər iki halda nəticə **eynidir** — `{"name": "süd", "brand": "Milla", "size_value": 1.0,
"size_unit": "l", ...}`. Fərq yalnız gözləmədədir. 64 saniyə "işləmir" demək
deyil: internetsiz maşında layihə hələ də tam işləyir.

### İki tələ: fallback səhvi GİZLƏDİR

Açarı qoyub `LLM_PROVIDER=claude` yazdıqdan sonra hər şey işləyirdi — `/health`
`"claude"` göstərirdi, cavablar düzgün gəlirdi. Amma Claude **bir dəfə də işə
düşməmişdi**: hər sorğu sükutla Ollama-ya düşürdü. Səbəb fallback-in özüdür —
o, xarici xidmətin dayanmasını gizlətmək üçün qurulub, ona görə bizim
konfiqurasiya səhvimizi də gizlədirdi.

| Tələ | Nə baş verirdi | Həll |
|---|---|---|
| **`temperature`** | `400 invalid_request_error: temperature is deprecated for this model` — Opus 5 / Sonnet 5 kimi yeni modellərdə sampling parametrləri çıxarılıb. Fallback 400-ü də "səhv" sayıb Ollama-ya keçirdi | `ai/llm.py` → `_TEMPERATURE_SUPPORTED`: yalnız köhnə modellərə (`haiku`, `claude-3`) göndərilir. Determinizmi `effort=low` + dəqiq prompt verir |
| **Cavabın formatı** | Ollama sadə sətir qaytarır, Claude isə **blok siyahısı** (düşünmə bloku + mətn bloku). Zəncirin ortasındakı `json.loads()` siyahını qəbul etmir: `TypeError: ... not list`. `.with_retry()` ikinci dəfə də eyni səhvi alırdı və sətir **atılırdı** | `ai/llm.py` → `message_text()`: LangChain-in `.text` xüsusiyyəti ilə hər iki formatdan təmiz mətn çıxarılır |

Üçüncü ayar isə səhv deyil, ölçüdür: **`LLM_CLAUDE_MAX_TOKENS`** Ollama-nın
`LLM_NUM_PREDICT`-indən ayrıdır, çünki Claude-un düşünmə tokenləri də həmin
tavana daxildir — 800 verilsə JSON yarımçıq kəsilə bilər. Bu, tavandır; ödəniş
real işlənmiş token qədərdir.

Hər üçü `tests/test_llm_fallback.py`-də **şəbəkəsiz** regressiya testi ilə
kilidlənib: saxta `ChatAnthropic` ilə hansı parametrlərin göndərildiyi yoxlanılır.

**Ad toqquşması tələsi:** ayarlar `CLAUDE_*` yox, **`LLM_CLAUDE_*`** ilə başlayır.
Səbəb real problemdir: Claude Code mühitində `CLAUDE_EFFORT` artıq təyin olunub
və bizim ayarımızı sükutla əvəz edirdi (`low` → `high`). Ümumi adlar başqa
alətlərlə toqquşur.

**Kurikulum qeydi:** 3-cü ayın mövzusu Ollama + Qwen-dir. Claude API scope-dan
kənardır və qəsdən **seçimli** edilib — defolt hələ də Ollama-dır, LCEL
öyrənməsi isə tam qorunur.

## Deployment (Docker / DigitalOcean)

```bash
cp .env.example .env      # INGEST_API_KEY-i MÜTLƏQ dəyiş
docker compose up -d
docker compose exec ollama ollama pull qwen3:4b
```

Ətraflı: [`deploy/README.md`](deploy/README.md) — droplet ölçüsü, real qiymət,
HTTPS, ehtiyat nüsxə, nə sınanıb / nə sınanmayıb.

| Qərar | Səbəb |
|---|---|
| `DATA_DIR` ilə tək volume | baza, kataloqlar, OCR mətni, keş bir yerdə — ehtiyat nüsxə natamam qalmır |
| Ollama portu dərc olunmur | autentifikasiyasız LLM serveri internetdə qalmamalıdır |
| `python:3.13-slim`, alpine yox | alpine-də pillow/lxml mənbədən kompilyasiya olunur (dəqiqələr) |
| Dil faylları image-də | `apt`-dakı `tesseract-ocr-aze` versiyası fərqli ola bilər; bizimki sınanıb |
| `HEALTHCHECK` → `/health` | həm baza, həm Ollama modeli yoxlanılır |
| Caddy, nginx yox | HTTPS bir sətirdir; SSE üçün `flush_interval -1` |
| Səs bonusu seçimlidir | image 684 MB → 1.25 GB; `--build-arg WITH_VOICE=true` |

**Ölçülmüş qiymət reallığı:** layihənin bahalı hissəsi LLM-dir. Yalnız BasketIQ
(dashboard + scraping + OCR) 1 GB droplet-də ~$6/ay işləyir; `qwen3:4b` əlavə
olunanda 8 GB lazımdır (~$48/ay). Kod dəyişmədən LLM-i kənarda saxlamaq olar —
yalnız `OLLAMA_BASE_URL` fərqlidir.

## Baza sxemi: `price_snapshots` və market birləşdirmə (v2)

### `price_snapshots` — gündəlik qiymət qatı

`prices` cədvəli bir KATALOQ sətrinə bağlıdır (`catalog_id NOT NULL`), yəni
yalnız həftəlik jurnaldan gələn qiyməti saxlaya bilir. Onlayn mağazadan
gündəlik çəkilən qiymətin kataloqu yoxdur — ona görə ayrıca cədvəl:

```sql
CREATE TABLE price_snapshots (
    id, product_id, store_id, price, unit_price,
    is_promo, source, observed_at
);
CREATE UNIQUE INDEX ux_snapshot_daily
    ON price_snapshots(product_id, store_id, source, date(observed_at));
```

`source` (`'site' | 'catalog'`) **həlledicidir**: sayt qiyməti ilə kataloq
iddiası eyni cədvəldədir, amma qarışmır. Endirim yoxlaması yalnız
`source='site'` sətirlərini oxuyacaq — kataloqun iddiasını yenə kataloqla
təsdiqləmək dairəvi məntiqdir. Sahə `CHECK` ilə qorunur: şərh heç nə
qorumur, üçüncü dəyər səssizcə yazılsaydı həmin sətirlər süzgəcdən kənarda
qalardı və bunu heç kim görməzdi.

**Unikal indeks ifadə üzərindədir (`date(observed_at)`), sütun üzərində yox.**
Sütun variantı heç nə tutmurdu: `observed_at` tam vaxt möhürü olduğu üçün eyni
məhsul saat 09:00 və 18:30-da çəkiləndə iki sətir yaranırdı və «hər gün bir
sətir» qaydası kağız üzərində qalırdı. Ölçüldü: ifadəli indekslə ikinci yazı
`IntegrityError` verir, ertəsi gün isə keçir.

**Cədvəl hazırda BOŞDUR** — onu dolduracaq mənbə yoxdur (bax «Mənbələr»).

### Dublikat market sətirlərinin birləşdirilməsi

Kataloq yüklənəndə market adı sərbəst mətndir və `get_or_create_store()` onu
SLUG üzrə axtarır. «Araz» əl ilə, «Araz Market» isə scraper tərəfindən
yaradılmışdı — **eyni şirkət, iki market**. Nəticə istifadəçi panelində
görünürdü: müqayisə cədvəlində iki ayrı sütun və «Araz Market səbətdəki
məhsulları satmır» yazısı.

`app/db.py:STORE_MERGES` siyahısı bunu həll edir (hər `init_db()`-də işləyən,
təkrar çağırıla bilən miqrasiya). Real bazada nəticə:

| | əvvəl | sonra |
|---|---|---|
| Araz | 8 qiymət, 1 kataloq | **191 qiymət, 2 kataloq** |
| Araz Market | 183 qiymət, 1 kataloq | **silindi** |
| cəmi qiymət | 551 | **551** |

Data itkisi **sıfır**. Siyahı ƏL İLƏ doldurulur: adları avtomatik oxşarlığa
görə birləşdirmək təhlükəlidir — «Bravo» ilə «Bravo Express» fərqli şəbəkə
ola bilər.

## Atribut çıxarma: qiymət ölçü kimi köçürülür (v3)

Sətirdə ölçü yazılmayanda model əlindəki yeganə rəqəmi — **qiyməti** — ölçü
sahəsinə qoyur:

```
«cay mi 1.25»                 -> ölçü 1.25 L, qiymət 1.25 ₼
«Persil Уи toz 1.35»          -> ölçü 1.35 kg, qiymət 1.35 ₼
```

**Bu, kosmetik deyil.** `unit_price` belə sətirlərdə **tam 1.0** çıxır — «1 litri
1 manat». Kataloqda ondan ucuz heç nə yoxdur, deməli saxta təklif «ən sərfəli»
sıralamasının **başına** keçir.

`price_reused_as_size()` (`ingestion/pipeline.py`) iki şərt yoxlayır: ölçü
qiymətə bərabərdirmi və həmin rəqəm sətirdə **yalnız bir dəfə** yazılıbmı.
İkinci şərt təsadüfi üst-üstə düşməni qoruyur — «Sirab su 1.5 L 1.50 ₼»
sətrində rəqəm iki dəfədir, deməli ölçü realdır. **Məhsul atılmır, yalnız ölçü
atılır:** qiymət realdır, onu itirmək olmaz.

Ölçüldü: 74 ölçülü sətirdən 3-ü tutuldu, 62-yə toxunulmadı, `unit_price = 1.0`
sətir sayı **3 → 0**.

### Sınanan və ATILAN variant: adın sətirdə əsaslandırılması

İlk fikir modelin çıxardığı adı xam sətirdə axtarmaq idi. Gözlə təsdiqlənmiş
60 hökmlə tutuşdurmaqla ölçüldü — altı variantın hamısı pis çıxdı, ən yaxşısı
belə **6 səhvdən 3-ünü tutub 50 doğrudan 10-nu atırdı**.

Səbəb: model bəzən dünya biliyi ilə **doğru** ad verir — «Heineken 4.35»
sətrindən «pivə». Sətirdə həmin söz yoxdur, amma ad düzdür. Ona görə yoxlama
tətbiq edilmədi.

---

## Matching (hibrid, 3 pillə)

| Pillə | Xərc | Nə edir |
|---|---|---|
| 1. `canonical_key` | pulsuz | "Milla süd 1000 ml" və "Süd Milla 1 L" → eyni açar |
| 2. Oxşarlıq süzgəci | pulsuz | cütlərin 94.9%-ni LLM-ə çatmadan atır |
| 3. LLM qərarı | ~2 san/cüt | "yumurta" ≟ "toyuq yumurtası" |

Süzgəcin ölçülmüş bölgüsü (`python tools/match_stats.py --reset`, 13 məhsul):

```
  Mümkün cüt (C(13,2))   :  78
  - ölçü ziddiyyəti      : -52     1 kq ≠ 500 q -> fərqli məhsuldur
  - oxşarlıq həddi altı  : -22     hədd 0.34
  = LLM-ə gedən          :   4
```

LLM-ə çatan 4 cütün hamısı mənalıdır — üçü eyni məhsulun fərqli yazılışı,
biri isə `«yumurta» ≟ «toyuq yumurtası»`, yəni məhz kodun həll edə bilmədiyi hal.

`--reset` niyə lazımdır? Matching bir dəfə işləyəndən sonra hər şey
qruplaşır və süzgəc 0 namizəd qaytarır. Alət `group_key`-i müvəqqəti sıfırlayır,
ölçür və `finally` blokunda geri qaytarır — ehtiyat nüsxə də fayla yazılır.

Süzgəc Azərbaycan dilinin **aqlütinativ** quruluşunu nəzərə alır: `düyü`/`düyüsü`,
`makaron`/`makaronu`, `yağ`/`yağı` — biri digərinin prefiksidirsə eyni kök sayılır.
`MIN_PREFIX=3` isə `su`/`süd` qarışmasının qarşısını alır.

## Səbət müqayisəsi

Müqayisə `product_id` üzərində yox, **`group_key`** üzərində aparılır — çünki eyni
məhsul hər marketdə ayrı sətirdir.

**Natamam market "ən ucuz" elan edilmir.** Səbətin 7 məhsulundan 6-nı satan market
cəmdə ucuz görünür, çünki çatışmayan məhsul 0 sayılır. Sistem əhatəni ayrıca göstərir
və yalnız tam səbəti olan marketlər arasında qalib seçir.

## Alətlər

```bash
# Sınaq üçün süni kataloq şəkli yaradır -> data/sample_catalog.png
python tools/make_sample_catalog.py

# Bir faylı uçdan-uca yoxlayır: OCR -> təmizləmə -> nəticə cədvəli
python tools/inspect_catalog.py data/sample_catalog.png
python tools/inspect_catalog.py kataloq.pdf --psm 4 --raw

# Scraping mənbəyini qiymətləndirir (robots.txt, statik/dinamik, text layer)
python tools/check_source.py https://example.az/kataloq

# Onlayn mağaza qatı: hansı çəkmə pilləsi işləyir (JSON/XHR -> BS4 -> Selenium)
python tools/check_source.py --all
python tools/check_source.py --store bravo --selenium

# Mənbədən kataloq çəkir
python tools/scrape.py araz --pages 2

# Matching süzgəcinin statistikası (--reset ilkin vəziyyəti ölçür)
python tools/match_stats.py --reset

# Səs əmrini uçdan-uca yoxlayır
python tools/voice_check.py qeyd.ogg

# Kataloq səhifələrindən məhsul şəkillərini kəsir -> app/static/images/products/
python tools/build_images.py
python tools/build_images.py --catalog 12 --force

# Qiymətsiz («yetim») məhsulları silir - kataloq yenidən emal olunandan sonra qalır
python tools/purge_orphans.py            # quru qaçış
python tools/purge_orphans.py --apply    # həqiqətən silir

# Marketi bazadan tamamilə silir (əvvəl ehtiyat nüsxə götürür)
python tools/purge_store.py <slug>          # quru qaçış: nə siləcəyini göstərir
python tools/purge_store.py <slug> --apply  # həqiqətən silir
```

## OCR dil faylları

`aze`, `rus`, `tur` dil faylları `data/tessdata/` qovluğunda saxlanılır və
`TESSDATA_PREFIX` ilə göstərilir — belədə `Program Files`-a admin hüququ ilə
toxunmaq lazım gəlmir.

## Etik qeyd

Yalnız ictimai olaraq dərc olunmuş kataloqlar emal olunur, `robots.txt`-ə
riayət edilir, sorğular arasında gecikmə qoyulur. Layihə təhsil məqsədlidir.

## Testlər öz bazasında işləyir (real səhvdən sonra)

`tests/conftest.py` `DATABASE_PATH`-i müvəqqəti fayla yönəldir — `app.config`
idxal olunmamışdan ƏVVƏL, çünki `conftest.py` pytest tərəfindən test
modullarından əvvəl oxunur.

**Niyə lazım oldu?** Əvvəl belə bir fayl yox idi və `pytest` birbaşa
`data/basketiq.db` üzərində işləyirdi. `test_mcp.py` və `test_voice.py` isə
belə başlayır:

```sql
DELETE FROM basket_items WHERE basket_id = 1;
INSERT INTO basket_items (basket_id, product_id, qty) VALUES (1, ?, ?);
```

`basket_id = 1` dashboard-un işlətdiyi səbətdir. Yəni **hər test qaçışı
istifadəçinin səbətini silib test məhsulları ilə əvəz edirdi**. Səhv tam
səssiz idi: testlər yaşıl keçirdi, sadəcə səhifədə tanımadığın məhsullar
görünürdü. Tapılma yolu da təsadüfi oldu — səbətdə iki naməlum məhsul
göründü və `basket_items`-ə yazan bütün kod axtarıldı.

**Nəticə:** 366 test keçir, 2-si atlanır (boş test bazasında məntiqli olaraq),
istifadəçinin datası toxunulmur.

**Bir mühit tələsi:** `.env` gitignore-dadır, yəni git worktree-yə köçmür və
`TESSERACT_CMD` boş qalır — həmin worktree-də 8 OCR testi `TesseractNotFoundError`
ilə **düşür**. Şrift tapılmayanda testlər ötürülür, tesseract tapılmayanda isə
düşür; eyni kateqoriyalı mühit boşluğu iki cür davranır. Həlli hələlik `.env`-i
worktree-yə köçürməkdir.

## Status

- [x] Həftə 1 — skelet, konfiqurasiya, DB sxemi, mənbə yoxlayıcı
- [x] Həftə 1 — manual upload + OCR + cleaner + upload UI
- [x] Həftə 1 — scraping (Araz) + kart-əsaslı layout analizi ¹
- [x] Həftə 2 — LangChain LCEL extraction zənciri + keş + normalizasiya
- [x] Həftə 2 — hibrid matching + səbət müqayisəsi
- [x] Həftə 3 — MCP serveri (10 alət) + n8n workflow
- [x] Həftə 3 — qiymət tarixçəsi qrafiki + endirim yoxlaması
- [x] Bonus — profil əsaslı tövsiyə (+3 MCP aləti, cəmi 13)
- [x] Bonus — Telegram səsli əmrlər (Whisper + regex/LLM təhlili)
- [x] Həftə 4 — Docker + compose + deployment sənədi ²
- [x] Bonus — Claude API (əsas) + Ollama (ehtiyat), LCEL fallback
- [x] Bonus — chain-of-thought filtri (xam model mətni brauzerə çatmır)
- [x] Bonus — UI redizayn: istifadəçi/admin ayrılığı, market və məhsul ikonları,
      exception-first endirim siyahısı
- [x] v2 — `robots.txt` oxuyucusu (RFC 9309) + `urllib`-dəki iki səhvin düzəlişi
- [x] v2 — dublikat market sətirləri birləşdirildi
- [x] v2 — `price_snapshots` cədvəli (gündəlik qiymət qatı üçün hazır, **boş**)
- [x] v2 — trolley dizayn sistemi + interfeysin sadələşdirilməsi (4918px → 1831px)
- [ ] v2 — baza qiymət (mağaza) qatı: **mənbə tapılmadı**, bax «Mənbələr» bölməsi
- [x] v3 — məhsul şəkilləri kataloqdan kəsilir (188 məhsuldan 60-ı, ≈32%)
- [x] v3 — şəkil uyğunlaşması bir-birə oldu + qiymət açarı məcburi: səhv
      şəkil 29% → **16%** (gözlə sayılıb, `logs/image-check.md`)
- [x] v3 — `layout.py`: qiymətsiz kart şəbəkədə xana tutur, sətirlər qarışmır
      (qarışıq kart 6 → 1); səhv şəkil **12%**
- [x] v3 — kataloq bütöv yenidən emal olundu (54 səhifə): səhv şəkil **10%**,
      doğru şəkil 50 — hər ikisi ən yaxşı göstərici
- [x] v3 — yetim (qiymətsiz) məhsullar silindi: 234 → 188, `tools/purge_orphans.py`
- [x] v3 — atribut çıxarma: qiymət ölçü kimi köçürülmür, saxta `unit_price = 1.0`
      sətir sayı 3 → **0**
- [x] v3 — kadrın sürüşməsi: sütun addımına alt hədd, kəsilən brend adları bərpa
      olundu (Flomaster, Heineken, Raffaello...)
- [x] v3 — interfeys Apple dizayn dilinə keçdi: yaşıl tam çıxarıldı, tək vurğu
      `#0071e3`, SF şrifti sistemdən, boz bölmə + ağ kart ritmi
- [x] v3 — `/search` səhifəsi: filtrlər ünvanda, menyu real datadan
- [x] v3 — ana səhifə trolley strukturuna keçdi (axtarış üstdə, endirimlər siyahı)
- [x] v3 — OBA marketi koddan, sənəddən və bazadan tamamilə silindi

¹ Mənbə seçimi ölçmə tələb etdiyi üçün Həftə 2-dən sonra tamamlandı.
² Real droplet-də yox, lokal Docker-də sınanıb — təfərrüat `deploy/README.md`-də.

**Testlər:** 409 — 407 keçir, 2 atlanır (`pytest -q`)
