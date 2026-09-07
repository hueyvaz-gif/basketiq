# BasketIQ — dizayn auditi (`design-critic`)

Tarix: 2026-09-07 · Auditor: `design-critic` (yalnız oxuyan)
Əhatə: `app/static/` — `style.css`, `index.html`, `app.js`, `analytics.js`,
`advisor.js`, `profile.js`, `scrape.js`, `nav.js`
(+ `app/models.py`, `app/analytics.py`, `app/api/basket.py` sərhəd yoxlaması üçün)

| | Say |
|---|---|
| **BLOKER** | 4 |
| **XƏBƏRDARLIQ** | 6 kateqoriya |
| **QEYD** | 9 |

---

## BLOKER

### B1 — bənövşəyi AI-dan kənarda işlədilib

`app/static/style.css:69`

```css
--ai: #7C3AED;          /* yalnız AI kartı */   (sətir 45)
--store-2: #7C3AED;                            (sətir 69)
```

`--store-2` **hərfbəhərf eyni hex-dir**. Market siyahısında ikinci gələn
marketin nöqtəsi/ikonu (`app.js:56` `store-mark`, `app.js:80` `store-dot`,
`app.js:641,661` bar avatarı, `analytics.js:59` qrafik xətti) AI kartı ilə eyni
bənövşəyidir. Faylın öz şərhi (`style.css:15`, «bənövşəyi = YALNIZ AI») bunu
inkar edir.

**Düzəliş:** `--store-2` üçün AI ilə kəsişməyən ton seç, `--ai`-dan gözlə
seçilən məsafədə saxla.

---

### B2 — market rəngi ADA yox, SIRA İNDEKSİNƏ bağlanıb

`app/static/app.js:72-77` və `app/static/analytics.js:62-67`

```js
// app.js:72
function storeColorVar(name) {
  if (!storeColorIndex.has(name)) {
    storeColorIndex.set(name, storeColorIndex.size % STORE_COLOR_COUNT);
  }
  return `var(--store-${storeColorIndex.get(name) + 1})`;
}
```

Map açarı addır, amma **dəyər ilk görülmə sırasından** (`storeColorIndex.size`)
gəlir — yəni rəng adın yox, backend-in qaytardığı sıranın funksiyasıdır.

Bu nəzəri deyil. `app/api/basket.py:221`:

```python
results.sort(key=lambda r: (not r["complete"], r["total"]))
```

Marketlər tamlıq + səbət cəminə görə sıralanır → səbətə bir məhsul əlavə edən
kimi sıra dəyişir → eyni market başqa `--store-N` alır. Səhifə yenilənəndə Map
sıfırlanır və rənglər yenidən paylanır. `app.js:59-68`-dəki şərh kodun etdiyinin
əksini iddia edir.

**İki müstəqil reyestr var:** `app.js:70` (`storeColorIndex`, API sırası) və
`analytics.js:60` (`storeColors`, `warmColors()` ilə əlifba sırası). API sırası
qiymətə görədir → eyni market cədvəldə bir rəngdə, qrafikdə **başqa rəngdə**.
`analytics.js:56-57`-dəki «eyni market qrafikdə və cədvəldə eyni rəngdə
görünsün» şərhi sınıqdır.

**Düzəliş:** rəngi addan determinist hesabla və hesablamanı **bir ümumi yerdə**
saxla ki, hər iki fayl eyni funksiyanı çağırsın.

---

### B3 — statik karta hover `transform`

`app/static/style.css:286-289`

```css
.stat { ... transition: box-shadow var(--ease), transform var(--ease); }
.stat:hover { box-shadow: var(--shadow-lift); transform: translateY(-2px); }
```

`.stat` kartları interaktiv deyil: `index.html:281-304`-də sadə `<div>`-lərdir,
`app.js:773-792` `renderStats()` onlara nə klik dinləyicisi, nə link, nə `role`
verir. Səhifənin ən yuxarısındakı 4 kart kursor altında qalxıb-enir — heç bir
hərəkət təklif etmədən. Qayda 12 məhz bunu qadağan edir.

`.card-lift` (`style.css:269-270`) isə **heç yerdə istifadə olunmur** — qalxma
effekti yalnız interaktiv olmayan elementə qalıb, interaktiv variant ölü koddur.

**Düzəliş:** `.stat:hover`-dan `transform`-u götür (yalnız `box-shadow` qalsın),
və ya `.stat`-ı həqiqətən interaktiv et.

---

### B4 — rəng stat kartlarında bəzək kimi işlədilib

`app/static/app.js:775-778`

```js
["package", "Məhsul", db.products, "AI ilə çıxarılmış sətir", "is-green"],
["tag",     "Qiymət", db.prices,   "Ümumi müşahidə",          "is-amber"],
```

«Məhsul» sayı qənaət/ən ucuz/təsdiqlənmiş deyil — sadəcə saydır, amma yaşıl
(`style.css:307`). «Qiymət» müşahidə sayı diqqət tələb etmir — amma kəhrəba
(`style.css:308`). Dördüncü kart sırf «hamısı mavi olmasın» deyə rənglənib;
`style.css:10-17` («Bir element "gözəl görünsün" deyə rənglənmir») ilə ziddir.
Üstəlik `index.html:281-304` skeleton `is-accent` ilə başlayır → yüklənəndə
rəng sıçraması olur.

> Auditorun qeydi: Qayda 1-in mətnində açıq BLOKER kimi yalnız «yaşıl brend
> mənasında» və «bənövşəyi AI-dan kənarda» sadalanıb. Bu hal «bəzək» bəndinə
> düşür — dar oxunuşda XƏBƏRDARLIQ sayıla bilər.

**Düzəliş:** dörd stat kartının hamısını `is-accent` et (neytral sayğaclardır).

---

## XƏBƏRDARLIQ

### Rəng semantikasının sərhədi

- `style.css:68` — `--store-1: #0071E3` = `--accent`. Brend/primary rəngi eyni
  zamanda birinci marketin kimlik rəngidir. B1 ilə eyni sinifdən problem.
- `style.css:71` — `--store-4: #B45309` = `--amber-ink` («təsdiqlənməyib» pill
  mətni, `style.css:460`). Status/kimlik ayrımı zəifləyir.
- `analytics.js:33-40` — token-lər `getComputedStyle` ilə oxunur (Qayda 3
  təmiz), amma **fallback-lar köhnə palitradandır**: `green: "#34C759"` (real
  `#16A34A`), `amber: "#FF9F0A"` (real `#F59E0B`), `text2: "#6E6E73"` (real
  `#4B5563`), `text: "#1D1D1F"` (real `#111827`). CSS gec yüklənsə qrafik
  səssizcə başqa palitraya düşür — sınmır, yalan rəngdə çəkir.
- `app.js:203` — `ocr_used ? "warn" : "ok"`. OCR işlədilməməsi «yaşıl»,
  işlədilməsi «kəhrəba». Bu status deyil, mənbə növüdür.
- `style.css:729` — `.icon-btn:hover { background: var(--red) }`. Qırmızı
  «bahalı/şübhəli/xəta» üçündür; silmə şərti olaraq bu ailəyə aiddir.

### Boşluq şkalası

`:root`-da 6 token (`--s1..--s6` = 4/8/16/24/32/48px), amma 10 token-dənkənar
dəyər işlədilir:

| Dəyər | Yerlər |
|---|---|
| `2px` | 627, 889, 1045, 1075 |
| `3px` | 883-885 (inset zolaq), 941 |
| `5px` | 177, 450, 618 |
| `6px` | 234, 324, 347, 412, 420, 436, 446, 753, 841, 908, 1043… (12+) |
| `10px` | 157, 193, 558, 995 |
| `11px` | 768, 776 |
| `12px` | 683, 788, 805 |
| `14px` | 597, 874, 768 |
| `18px` | 193, 372 |
| `22px` | 683 |

`6px` faktiki olaraq gizli 7-ci token-dir (4px ilə 8px arasında).
`11/12/14px` üçlüyü eyni işi görən üç fərqli dəyərdir.

### Font ölçüsü şkalası

15 fərqli ölçü: 11, 12, 13, 14, 15, 16, 17, 19, 21, 26, 30, 32, 34, 36, 56.
Bir dəfə işlədilənlər: **19px** (170), **21px** (231), **26px** (346),
**32px** (978), **34px** (424), **36px** (318).
**30/32/34/36 dördlüyü** xüsusilə problemlidir — 4 element 2px fərqlə, göz onları
eyni səviyyə kimi oxuyur, 4 addım heç bir iyerarxiya qazandırmır.

### `!important`

4 yer: `128` (`.hidden`), `250` (`.flush`), `738` (`.actions.flush`),
`1098-1100` (`prefers-reduced-motion`). Birinci və sonuncu əsaslıdır.
`.flush` iki dəfə təkrarlanır — `.actions { margin-top: var(--s3) }` (737)
spesifiklikdə üstün gəldiyi üçün. `!important` burada quruluş problemini örtür.

### Mətn eni (`--measure` tətbiq olunmayan yerlər)

`--measure: 68ch` (`style.css:91`) — **özü 65 həddini aşır**.
Tətbiq edilməyən bloklar: `326` `.stat-note`, `412` `.hero-price-note`
(`app.js:550-553` uzun cümlə yığır, 1280px-də ~90+ simvol), `889`
`.exception-why` (`analytics.js:380` `reasons.join(" · ")`), `1075`
`.status-detail`, `583` `.dz-sub`.

### Mobil / 380px

`@media (max-width: 640px)` **qəsdən yoxdur** (`style.css:1079-1088`-də
sənədləşdirilib) — ona görə bloker deyil. Ölçülən nəticələr:

- `.wrap` padding 24px×2 → 380px-də 332px faydalı en.
- `style.css:510` `.bar-row` — 96 + 16 = 112px sabit, bara 220px qalır;
  `.bar-value` qısa barlarda çıxıntı verir.
- `style.css:370-374` `.ribbon { width: 200px; right: -52px }` — **sabit en**,
  «Bölünmüş alış» mətni qalib adının üstünə düşür.
- `style.css:1090-1093` 1000px-də `.stat-grid` 2 sütun → 380px-də xana ~158px,
  `.stat-value` 36px + `.stat-icon` 38px → 5 rəqəmli say kəsilir.
- `table.lines` `.table-scroll` içindədir → üfüqi sürüşür, sınmır. ✓

### Digər

- `profile.js:103` — inline `style="opacity:.8"`, halbuki `.is-muted`
  (`style.css:254`) mövcuddur.
- `advisor.js:30` — `btn.textContent = "Yazılır…"` SVG-ni silir, düymə eni
  sıçrayır. `scrape.js:47-49` eyni problemi `innerHTML` ilə həll edir —
  iki fayl arasında ziddiyyətli yanaşma.

---

## QEYD

- `index.html:13-18` — şərh «Inter» deyir, `<link>` **Manrope** yükləyir. Inter
  heç vaxt endirilmir, praktiki olaraq ölü fallback-dır.
- `index.html:11` — favicon data-URI-də `stroke='%230071E3'` əl ilə təkrarlanıb;
  token dəyişəndə favicon geridə qalır (səssiz drift).
- `app.js:55` — `store-chip is-best` sinfi generasiya olunur, amma
  `.store-chip.is-best` qaydası CSS-də **yoxdur**. Ölü sinif (məlumat itmir,
  xanalar `price-pill.is-best` ilə işarələnib).
- **Ölü CSS:** `.card-lift` (269-270), `.pill.solid-green` (466),
  `.avatar.is-red` (655), `.pill.is-accent` (462).
  `.avatar.is-red` xüsusilə: `app.js:801-802` `state === false` halında
  `tone = ""` verir → **xəta halında avatar rəngsiz qalır**, halbuki qırmızı
  variant mövcuddur.
- `analytics.js:191` — `label` callback-i boş `": "` ilə bitir; hər iki qrafik
  növü sonradan əvəz edir (232-234, 272-273) → ölü kod.
- `analytics.js:44` — `alpha()` regexp-i yalnız 6 rəqəmli hex tanıyır; token
  `rgb()`/3 rəqəmli formata keçsə şəffaflıq səssizcə itir.
- `analytics.js:361-367` — sayğac 4 pilldir, amma `endirim_yoxdur` hökmü
  sayğacda yoxdur, halbuki siyahıda (`analytics.js:336`) rank 2 ilə iştirak edir.
- `.notice` bloklarında `aria-live` yoxdur (`style.css:786`, `app.js:85-87`) —
  status mesajları asinxron dəyişir, ekran oxuyucusu elan etmir.

---

## ƏMİN DEYİLƏM

- **380px-də faktiki render** — brauzer işə salınmadı, ölçülər CSS-dən
  hesablanıb. `.ribbon` və `.stat-value` kəsilməsi ekran görüntüsü ilə
  təsdiqlənməyib.
- **`tests/test_ui_contract.py`-ın nə ölçdüyü** — fayl mövcuddur, məzmunu bu
  auditda oxunmadı. Qayda 6 nəticəsi yalnız `style.css` `font-size` dəyərlərinin
  statik müqayisəsinə əsaslanır.
- **Qayda 4 (dark mode)** — yalnız `app/static/*.css` yoxlanıldı.
- **B4-ün təsnifatı** — BLOKER/XƏBƏRDARLIQ sərhədindədir (yuxarıdakı qeydə bax).

---

## XÜLASƏ

**Ümumi dizayn sağlamlığı: yaxşı, amma iki yerdə niyyət ilə kod ayrılıb.**

Güclü tərəflər ölçülə biləndir: CSS-də `:root` xaricində **bir dənə də**
hardcode hex/rgb yoxdur (Qayda 2 tam təmiz), qrafik rəngləri `getComputedStyle`
ilə oxunur (Qayda 3), dark mode qəsdən və şərhlə yoxdur (Qayda 4), hər paneldə
tam bir primary düymə var (Qayda 5), 56px verdict təkdir (Qayda 6), ən ucuz
xana yaşıl + ✓ + `sr-only` üçlüyünü saxlayır (Qayda 7), natamam sütun zolaqlıdır
(Qayda 8), exception-first sırası qorunur (Qayda 9), uydurma loqo yoxdur
(Qayda 11), `CATEGORIES` ↔ `CATEGORY_ICON` və `VERDICTS` ↔ `VERDICT` xəritələri
hərfbəhərf üst-üstə düşür (Qayda 13-14).

Ən ciddi problem **B2**-dir: rənglər sıra indeksinə bağlanıb, backend isə sıranı
qiymətə görə çeşidləyir → səbətə məhsul əlavə edən kimi rənglər sürüşür, üstəlik
cədvəl və qrafik iki ayrı reyestr işlətdiyi üçün eyni market iki blokda iki
fərqli rəngdə görünür.

**Diqqətçəkən nümunə:** hər üç əsas blokerdə **koddakı şərh doğru qaydanı izah
edir, kod isə onu etmir** — sənəd hazırdır, icra geridə qalıb.

---

## TƏTBİQ VƏZİYYƏTİ (auditdən sonra, `master`)

| | Vəziyyət | Qeyd |
|---|---|---|
| **B1** | ✅ düzəldilib | `--store-2: #7C3AED` → `#4338CA` |
| **B2** | ✅ düzəldilib | Yeni `app/static/store-colors.js` — yeganə mənbə; `app.js` və `analytics.js` onu çağırır |
| **B3** | ✅ düzəldilib | `.stat` və `.stat:hover`-dan `transform` çıxarıldı |
| **B4** | ✅ düzəldilib | Dörd stat kartı da `is-accent` |
| XƏBƏRDARLIQ | ⬜ toxunulmayıb | Qərar istifadəçinindir |
| QEYD | ⬜ toxunulmayıb | Qərar istifadəçinindir |

### B2-nin son həlli

Hash xananı **təklif edir**, toqquşma **xətti sınaqla** (linear probing) həll
olunur; sınaq market adlarının **əlifba sırasında** aparılır — əlifba API
sırasından asılı olmadığı üçün nəticə giriş sırasından asılı deyil.
Təmiz hash bunu verə bilmirdi: real 6 market adı 6 xanadan yalnız 3-nə düşürdü.

Müstəqil yoxladım (`node` ilə, modulun özünü işlədərək):

| Yoxlama | Nəticə |
|---|---|
| Eyni dəst, 4 fərqli sıra → eyni xanalar | ✅ |
| 6 market → 6 fərqli xana | ✅ toqquşma yoxdur |
| `basket.py` qiymət sırası ilə eyni nəticə | ✅ |
| 5 → 6 market keçidində rəngi dəyişən | **0** |
| `analytics.js`-də ayrıca reyestr | yoxdur (tək mənbə) |

`tests/test_store_colors.py` — 10 test (5 statik, 5 `node` ilə real icra,
`node` yoxdursa `skipif`).

### Maşın qapısı

```
pytest -q      → 292 keçdi, 8 keçildi   (əvvəl 282/8)
ruff check .   → All checks passed!     (exit 0)
```

`ruff` 0.16.6 quruldu və `ruff.toml` yazıldı (`select = E,F`, `ignore = E501`).
Konfiqurasiyasız ruff 94 xəta verirdi — qapı heç bir tapşırığı buraxmazdı.

### `scripts/night.sh` düzəlişləri

- `:67` — `--verbose` əlavə olundu. Bunsuz `claude -p` hər çağırışda
  `--output-format=stream-json requires --verbose` xətası ilə dərhal çıxırdı,
  yəni **heç bir agent işləmirdi**.
- `:33-40` — worktree yaradılandan sonra `.env` kopyalanır. Bunsuz
  `TESSERACT_CMD` təyin olunmurdu və 8 OCR/scraper testi sınırdı, yəni qapı
  heç vaxt keçmirdi.
