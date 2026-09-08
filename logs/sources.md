# Mağaza qatı — mənbə yoxlaması (Addım 1)

Tarix: 2026-09-08 · Alət: `python tools/check_source.py --all`
User-Agent: `BasketIQ-Student-Project/1.0 (educational)` · Gecikmə: 2.0 san

Bu sənəd **ölçmə nəticəsidir**, fərziyyə deyil. Hər rəqəm yuxarıdakı əmrin
çıxışından gəlir və təkrar işlədilə bilər.

---

## Nəticə cədvəli

| Market | robots.txt | Səhifə | HTML | mətn | link | Qiymət HTML-də | Pillə |
|---|---|---|---|---|---|---|---|
| **Araz** | icazə ✓ | Next.js, client-render | 1.46 MB | 634 simvol | çox | **yox** | **YOX** |
| **Bravo** (Umico) | icazə ✓ | Nuxt, client-render | 112 KB | 1 819 simvol | çox | **yox** | **3 · Selenium** |
| **Bazarstore** | icazə ✓ | baxım elanı | 20 KB | 377 simvol | **1** | yox | **YOX** |

Yoxlanan ünvanlar:

- Araz — `https://www.arazmarket.az/az/categories/quru-meyveler-2`
- Bravo — `https://umico.az/categories/4497-dukan`
- Bazarstore — `https://bazarstore.az/`

---

## Market üzrə izah

### Araz — baza qiymət qatı MÜMKÜN DEYİL

Öz onlayn mağazası var, `sitemap-products-1.xml`-də **15 000 `<loc>`** (az/en/ru
üçlükləri ilə, təxminən 5 000 məhsul). Amma:

- Kateqoriya səhifəsi də, məhsul səhifəsi də **client-render**-dir — 1.46 MB
  HTML-in içində cəmi 634 simvol mətn, məzmun yerinə `Loading...`.
  Qiymət nə HTML-də, nə JSON-LD-də, nə `og:price`-da var. → **2-ci pillə düşür.**
- Datanın gəldiyi ünvanlar `robots.txt` ilə **açıq qadağandır**:

      Allow: /
      Disallow: /api/
      Disallow: /_next/

  → **1-ci pillə (JSON/XHR) qadağandır.**
- Selenium da işlədilmir. Səbəb tapşırığın öz qaydasıdır: brauzer səhifəni
  render edəndə həmin qadağan ünvanları özü çağırır, yəni «yalnız səhifəni
  açdım» deyib qadağanı dolayı yolla keçmək olardı. Kod bunu `_selenium_allowed()`
  funksiyasında açıq şəkildə rədd edir. → **3-cü pillə də bağlıdır.**

**Nəticə:** Araz üçün `source='site'` qatı bu qaydalarla alınmır. Araz yalnız
**kataloq (iddia) mənbəyi** olaraq qala bilər — mövcud PDF/OCR yolu işləyir və
`/az/discount-magazine` səhifəsi robots ilə açıqdır.

### Bravo — mümkün, amma Selenium tələb edir

- `bravosupermarket.az` **öz onlayn mağazası deyil** — marketinq saytıdır.
  Sitemap-i 2023-cü ildən qalıb və yalnız `special-offers` səhifələridir.
  Onlayn satış `umico.az/categories/4497-dukan` üzərindən gedir (saytın öz
  «Onlayn market» linki oradadır), ikinci kanal Wolt-dur.
- `umico.az/robots.txt` kateqoriya səhifələrinə icazə verir və səhifələməni
  **açıq şəkildə** açıq saxlayır (`Disallow: /*?*` + `Allow: /*?page=*`).
- Qiymət ilk HTML-də yoxdur (Nuxt), açıq data ünvanı da tapılmadı →
  **3-cü pillə: Selenium.** Qadağan ünvan yoxdur, ona görə Selenium icazəlidir.

**Ölçülməyib:** Selenium ilə real render nəticəsi, bir kateqoriyanın məhsul
sayı və vaxtı. Bu, 4-cü addımın işidir.

### Bazarstore — hazırda mümkün deyil

Bütün sayt (`/robots.txt` daxil) eyni cavabı qaytarır:

> «Saytda yenilənmə işləri aparılır… Saytımız qısa müddət ərzində yenidən
> xidmətinizdə olacaq.»

Səhifədə cəmi **1 link** var (`mailto:`). Çəkiləcək məhsul yoxdur. Sayt
qayıdanda yenidən yoxlanmalıdır — kod hazırdır, `SHOPS` qeydiyyatında durur.

---

## Yol boyu tapılan İKİ SƏHV (kodda düzəldildi)

Hər ikisi `urllib.robotparser`-dədir və hər ikisi bu layihənin əsas etik
qaydasına toxunur. Yeni modul: `ingestion/robots.py`, testlər:
`tests/test_robots.py` (12 test).

### 1. Kitabxana öz adı ilə gedir, 403 alır, «hər şey qadağan» yazır

`RobotFileParser.read()` faylı urllib ilə çəkir və özünü `Python-urllib/3.13`
kimi təqdim edir. Ölçülüb: `umico.az` və `bravosupermarket.az` bu ada **403**
qaytarır. Kitabxana 403-ü `disallow_all = True` kimi qeyd edir.

Nəticə: robots.txt-də `Allow: /` yazan sayt bizim kodda QADAĞA görünürdü.

> **Bu, README-dəki «Bravo — QADAĞA ✗» qeydinin çox güman səbəbidir.**
> `bravosupermarket.az/robots.txt` faktiki olaraq belədir:
>
>     User-agent: *
>     Disallow: /bravo.jis.az/
>     Allow: /
>
> Yəni yalnız bir alt-yol bağlıdır. README bunu «ölçülmüş fakt» kimi
> saxlayırdı — fakt yanlış idi. **Addım 2-də README-də düzəldildi.**

**Həll:** robots.txt öz dürüst User-Agent-imizlə çəkilir (sorğularımızı da elə
həmin ad ilə göndəririk — gizlətmə yoxdur), status kodları standart üzrə
oxunur: 401/403 → hamısı qadağan, 404/410 → icazə, 5xx → naməlum.

### 2. Birinci uyğunluğu götürür, ən uzununu yox

`arazmarket.az/robots.txt`-də `Allow: /` sətri `Disallow: /api/`-dən **əvvəl**
gəlir. `urllib` sıra ilə yoxlayır, `Allow: /` hər şeyə uyğun gəlir və dərhal
«icazə var» deyir — yəni `Disallow: /api/` **heç vaxt işə düşmür**.

RFC 9309 isə **ən spesifik (ən uzun) qayda qalib gəlir** deyir.

Ölçmə: köhnə kodla `https://www.arazmarket.az/api/` → `icazə=True` (yanlış),
yeni kodla → `icazə=False` (düzgün).

Bu səhv birincidən **daha təhlükəlidir**: birincisi bizi lazımsız yerə
məhdudlaşdırırdı, ikincisi isə real qadağanı görünməz edirdi.

**Testlə təsdiq:** hər iki davranış mutasiya ilə yoxlanıldı — «ən uzun
uyğunluq» məntiqi birinci-uyğunluğa çevriləndə 3 test düşür, `$` lövbəri
söndürüləndə 1 test düşür. Yəni testlər regresiyanı həqiqətən tutur.

### `scraper.py` — addım 2-də bağlandı

`ingestion/scraper.py:robots_allows()` eyni iki səhvi daşıyırdı (real çəkilişi
idarə edən funksiya odur). **Addım 2-də `ingestion/robots.py`-a bağlandı.**

---

## Testlər

`pytest -q` → **305 keçdi / 8 keçildi** (əvvəl 293/8). Sınan test yoxdur.
Yeni 12 test şəbəkəyə çıxmır — robots.txt mətnləri sabit sətir kimi saxlanılır.

---

## İnsan qərarı gözləyən suallar (Addım 2)

1. **Araz baza qiymət qatı olmadan qalır.** Üç variant var: (a) Araz yalnız
   kataloq/iddia mənbəyi kimi saxlanılır; (b) Araz-a rəsmi icazə/API üçün
   müraciət edilir; (c) Araz tamamilə çıxarılır. Layihənin mövcud datasının
   böyük hissəsi Araz-dandır — (a) ən az itki verən yoldur.
2. **Bravo Umico üzərindən gəlir.** Qiymət «Bravo-nun mağaza qiyməti» yox,
   «Bravo-nun Umico-dakı qiyməti»dir. Bu fərq UI-da yazılmalıdır (8.5-dəki
   dürüstlük qeydi ilə eyni məntiq).
3. **Bazarstore gözləyir.** Sayt qayıdana qədər üç market yox, iki market var.

---

# Addım 2 — mənbə qərarı tətbiq olundu

Tarix: 2026-09-08 · Qərar: **Araz kataloq mənbəyi kimi qalır** (istifadəçi seçimi)

## Qat bölgüsü (yekun)

| Market | Kataloq (iddia) qatı | Mağaza (baza qiymət) qatı |
|---|---|---|
| **Araz** | ✓ `arazmarket.az/az/discount-magazine`, 1 PDF × 54 səh. | ✗ data ünvanı robots ilə qadağan |
| **Bravo** | ✗ `special-offers` Angular-dır, statik HTML-də PDF/şəkil linki **0** | ✓ Umico üzərindən (Selenium, addım 4-də ölçüləcək) |
| **Bazarstore** | ✗ | ✗ sayt baxımdadır |
| OBA | çıxarıldı | — |

Bravo-nun kataloq səhifəsi bu addımda ayrıca yoxlanıldı
(`check_source.py https://bravosupermarket.az/special-offers/`): robots icazə
verir, HTTP 200, 91 KB HTML, 6 978 simvol mətn, `ng-app`, **PDF link 0,
şəkil link 0**. Yəni Bravo-nun kataloq qatı olmamasının səbəbi qadağa deyil,
kataloq faylının statik HTML-də ümumiyyətlə olmamasıdır.

## Dəyişdirilən fayllar

| Fayl | Dəyişiklik |
|---|---|
| `ingestion/robots.py` | **YENİ** (addım 1-də yaranmışdı) — RFC 9309 oxuyucusu |
| `ingestion/scraper.py` | `robots_allows()` artıq `urllib.robotparser` işlətmir; OBA mənbəyi silindi; modul başlığındakı cədvəl yeniləndi |
| `tools/check_source.py` | mağaza qatı rejimi (addım 1) |
| `tools/scrape.py` | CLI nümunələri `oba` → `araz` |
| `n8n/basketiq-gunluk.json` | gündəlik axın `menbe: "oba"` → `"araz"` |
| `ingestion/layout.py` | ölçmələr saxlanıldı, «OBA əsas mənbədir» iddiası düzəldildi |
| `tests/test_scraper.py` | mənbə siyahısı testi: `araz` var, `oba` **yoxdur** |
| `tests/test_mcp.py` | eyni — iki MCP testi |
| `README.md` | mənbə cədvəli iki qatla yenidən quruldu; «Bravo qadağalıdır» səhvi açıq şəkildə düzəldildi |

`stores` üçün ayrıca seed siyahısı yoxdur — marketlər kataloq yüklənəndə
`ingestion/ingest.py:107`-də yaranır. Ona görə OBA-nı «seed-dən silmək» lazım
gəlmədi; bazadakı 352 OBA qiyməti toxunulmadan qalır.

## Maşın qapısı

`pytest -q` → **305 keçdi / 8 keçildi** (dəyişmədi), `ruff check .` → təmiz.

## ⚠ İNSAN BAXMALIDIR

**Bazada eyni market iki dəfədir.** `stores` cədvəli:

| id | ad | qiymət sayı |
|---|---|---|
| 2 | Bravo | 8 |
| 15 | **Araz** | 8 |
| 112 | OBA | 352 |
| 125 | **Araz Market** | 183 |

`Araz` və `Araz Market` eyni şirkətdir, amma iki ayrı market kimi sayılır —
istifadəçi panelindəki müqayisə cədvəlində hər ikisi ayrı sütun kimi görünür və
«Araz Market səbətdəki məhsulları satmır» yazısı məhz bundan doğur.

Bu, v2 tapşırığında yazılmayıb və avtomatik həll edilməyib: iki sətri
birləşdirmək **data miqrasiyasıdır** (183 + 8 qiymət, `group_key`-lər, səbət
sətirləri). Qərar insanındır — birləşdirilsin, yoxsa ad normallaşdırması
yalnız yeni yazılara tətbiq olunsun?

---

# Addım 4 — mağaza qatı ölçüldü: MƏNBƏ TAPILMADI

Tarix: 2026-09-08 · Hədəf: Bravo-nun bir kateqoriyası (Selenium)

Addım 2-də Bravo «mağaza qatı var» kimi qeyd olunmuşdu, çünki `umico.az`
robots icazə verirdi və səhifə açılırdı. **Bu qeyd səhv idi** — səhifənin
açılması orada məhsul olması demək deyil. Aşağıdakı ölçmələr bunu göstərdi.

## Ölçmə cədvəli

| Nə yoxlanıldı | Vaxt | Nəticə |
|---|---|---|
| `umico.az/categories/4497-dukan` (Bravo-nun öz saytındakı link) | 48 san render | **«0 məhsul»** — «Seçilmiş parametrlərə uyğun məhsul yoxdur» |
| `wolt.com/az/discovery/aze_bravo_supermarket` | 14–25 san | 17 Bravo filialı, hər birində «10000+ məhsul» |
| Wolt venue səhifəsi (Bülbül pr.) | 20–30 san | 40 kateqoriya linki, məhsul ADLARI başlıqlarda görünür, **qiymət 0** |
| Wolt kateqoriya səhifəsi (`items/yumurtalar-13`) | ~15 san | Kataloq **çatdırılma ünvanı arxasındadır** |
| `bazarstore.az` (təkrar yoxlama) | — | hələ də baxımdadır, səhifədə 1 link |

## Wolt niyə alınmır

Şəbəkə jurnalı: kateqoriya səhifəsində YALNIZ statik asset sorğuları gedir
(`wolt-com-static-assets.wolt.com/*.js|css`). Məhsul datası üçün heç bir sorğu
atılmır, çünki səhifə gözləyir:

> «Yerinizin təyin olunmasına icazə verin — Küçə və nömrəni daxil edin»

Yəni kataloq **çatdırılma ünvanı formasının arxasındadır**. Onu keçmək üçün
üçüncü tərəf saytına uydurma ünvan daxil etmək lazım gələrdi. Bu, nə texniki
məsələdir, nə də robots məsələsi — sadəcə edilməyəcək bir şeydir.

## İkinci, daha vacib etiraz

Wolt işləsəydi belə, oradakı rəqəm **çatdırılma platformasının qiymətidir**,
Bravo-nun rəfindəki qiymət deyil (platforma əlavəsi var). Onu «Bravo-nun
qiyməti» kimi göstərmək məhz bu layihənin etməkdən imtina etdiyi şeydir:
rəqəmi olduğundan başqa cür təqdim etmək.

## Sürət ölçməsi

Render başına **20–50 saniyə**. Tapşırığın 3.4 bəndi bir marketdən ~200
sorğu nəzərdə tuturdu — bu sürətlə **1.5–2.8 saat**, hər gün. Bu, mənbə
tapılsaydı belə ayrıca həll tələb edərdi.

## Yekun

| Market | Baza qiymət (mağaza) qatı | Səbəb |
|---|---|---|
| Araz | **yox** | robots `/api/` və `/_next/` qadağan edir |
| Bravo | **yox** | Umico kateqoriyası boş; Wolt ünvan arxasında + qiymət semantikası yanlış |
| Bazarstore | **yox** | sayt baxımdadır |

**Tapşırığın 3.2 bəndindəki «baza qiymət qatı» bu üç marketlə qurula bilmir.**
Bu, kodun çatışmazlığı deyil — ölçülmüş vəziyyətdir. `price_snapshots` cədvəli
(addım 3) yerində qalır və hazırdır; onu dolduracaq mənbə yoxdur.

## Buna bağlı olan addımlar

- **6** (endirim yoxlaması sayt datasına bağlansın) — mənbəsiz mümkün deyil.
- **7** (qat ayrımı ilə səbət müqayisəsi) — eyni səbəb.
- **5** (bloklamalı matching) — miqyas problemi minlərlə məhsul üçün idi;
  540 məhsulda bloklamanın ölçüləcək faydası yoxdur.
- **8** (interfeys) və **9** (README) — mənbədən ASILI DEYİL, indi edilə bilər.
