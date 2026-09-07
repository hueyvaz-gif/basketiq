# Səhər hesabatı

## [2026-09-08] dizayn blokerləri (B1-B4) + maşın qapısının bərpası — `dcbd80b`

- **Dəyişən fayllar:** 21 (+853 / -48)
  (tapşırıq mətnində +808 yazılmışdı; `git show --shortstat` 853 verir)
- **Testlər:** 282 → **292 keçdi, 8 keçildi, 0 sındı**
- **Yeni test:** `tests/test_store_colors.py` — 10 test
  (5 statik, 5 `node` ilə real icra; `node` yoxdursa `skipif`)
- **Dizayn auditi:** 4 BLOKER → **4-ü də düzəldilib**;
  XƏBƏRDARLIQ (6 kateqoriya) və QEYD (9) qəsdən toxunulmayıb
- **Yeni fayllar:** `app/static/store-colors.js`, `ruff.toml`,
  `tests/test_store_colors.py`, `logs/review.md`, `logs/notes.md`,
  `logs/commit-msg.txt`

---

### INSAN BAXMALIDIR

**1. Test öz adının vəd etdiyini yoxlamır.**
`tests/test_store_colors.py:222` — `test_qeyd_olunmamış_ad_da_xana_alır`.
Docstring deyir: «`note()` çağırılmasa belə `slot()` etibarlı xana verməlidir».
Amma `DRIVER` (sətir 57) hər ssenaridə əvvəlcə `SC.note(names)` çağırır, yəni ad
`slot()`-a çatanda ARTIQ qeydiyyatdadır. `slot()`-un öz-özünü qeyd edən qolu
(`store-colors.js:90`) heç vaxt işə düşmür. Test yaşıldır, yoxladığı yol isə
örtülməmiş qalır. Sürücüyə `note`-suz ssenari lazımdır.

**2. `.env` worktree-yə kopyalanır, worktree isə heç vaxt silinmir.**
`scripts/night.sh:38` `.env` faylını `$WORK`-a kopyalayır; `$WORK` isə
`$REPO/../basketiq-night-*` — repo-dan KƏNARDA, yəni `.gitignore` onu qorumur.
Skriptdə nə `git worktree remove`, nə `trap`, nə təmizləmə var. Hər gecə növbəsi
`ANTHROPIC_API_KEY` və `INGEST_API_KEY`-in açıq mətn nüsxəsini diskdə qoyur və
onlar yığılır. (Hazırda qalıq yoxdur — `ls ../basketiq-*` boşdur.)
Ya skriptin sonuna təmizləmə, ya da `.env`-in yalnız lazımi açarlarla
filtrlənərək kopyalanması lazımdır.

**3. `ruff` yeni asılılıqdır, `requirements*.txt`-də yoxdur - və qapı onu
səssizcə buraxır.**
`scripts/night.sh:54` lint addımını şərt içinə salıb:

    if "$PY" -m ruff --version >/dev/null 2>&1; then
      "$PY" -m ruff check . > logs/ruff.txt 2>&1 || { echo "ruff"; return 1; }
    fi

`ruff` qurulmayıbsa şərt yalan olur və lint qapısı heç bir siqnal vermədən
keçir - log-da da iz qalmır. `ruff==0.16.6` nə `requirements.txt`-də, nə
`requirements-voice.txt`-dədir. Təmiz mühitdə (və ya venv yenidən qurulanda)
qapının yarısı sükutla yox olur. Ən azı `else` qoluna «ruff yoxdur»
xəbərdarlığı və requirements-ə bir sətir lazımdır.

**4. Yeganə mənbə faylının şərhindəki ölçmə rəqəmi yanlışdır.**
`app/static/store-colors.js:17-19` deyir: «6 xanadan yalnız **4-nə** düşürdü -
**2 cüt** toqquşurdu». `node` ilə təmiz djb2-ni real altılıqda işlətdim:

    Araz:1  Araz Market:3  Test Market:5  Bravo:5  OBA:5  Test Scrape Market:5

Yəni **3 fərqli xana**, xana 5-də **4 ad birdən**: «2 cüt» deyil, bir dördlük.
`logs/review.md:34`, `logs/notes.md`, `tests/test_store_colors.py:38` və commit
mesajı - hamısı düzgün «3» yazır. Səhv rəqəm məhz kodun yanındakı şərhdədir,
yəni ən çox oxunacaq yerdə.

**5. 7-ci market MÖVCUD marketlərin rəngini sürüşdürür - ölçdüm, testi yoxdur.**
`logs/notes.md:60-63` «bunun nə qədər tez-tez baş verdiyini ölçmədim» yazır.
`rebuild()` əlifba sırası ilə hamısını yenidən paylayır, ona görə ölçdüm:

| 6-lığa əlavə olunan | rəngi dəyişən mövcud market |
|---|---|
| `Zeytun` | 0 / 6 |
| `Favorit` | 1 / 6 |
| `Neptun`, `Rahat`, `Spar` | **2 / 6** |
| `Kontinental` | **3 / 6** |

Tək bir yeni market palitranın yarısına qədərini yenidən paylaya bilər -
istifadəçinin «Bravo = göy» yaddaşı elə bu halda pozulur. `5 -> 6` keçidi isə
həqiqətən **0/6**-dır (review.md-dəki iddia təsdiqləndi). 12 marketdə də
`slot()` sərhəddən çıxmır və `undefined` qaytarmır (yoxlandı) - pozulma yalnız
rəng təkrarıdır. Bu davranışı kilidləyən test yoxdur.

**6. `ruff.toml`-da E501-in söndürülmə əsaslandırması öz konfiqurasiyasına ziddir.**
Şərh deyir: «E,F dəstindəki 141 xətanın 130-u məhz budur». Bu rəqəm ruff-un
STANDART 88 limitinə aiddir (ölçdüm: 131). Halbuki elə həmin fayl
`line-length = 100` təyin edir, 100-də isə cəmi **13** sətir uzundur:

    4  ai/matcher.py           2  ingestion/normalize.py
    2  tests/test_matcher.py   1  ingestion/ocr.py
    1  tests/test_chains.py    1  tests/test_basket.py
    1  tests/test_sanitize.py  1  ai/prompts.py  (140 simvol - ən pisi)

`ai/prompts.py:31` JSON sxem sətridir, bölünməsi mənasızdır. Yəni real
oxunaqlıq problemi GİZLƏNMİR; sadəcə `ignore = ["E501"]` 13 sətir üçün lazım
deyildi. Ya şərhdəki rəqəm düzəldilməli, ya da E501 açılıb 13 sətir həll
edilməlidir.

**7. `storeDot` ölü koddur və bu commit onu redaktə etdi.**
`app/static/app.js:69` - təyin olunub, layihədə heç bir çağırış yeri yoxdur
(`grep -rn "storeDot" app/ tests/` yalnız təyini tapır). Commit onu
`StoreColors.cssVar()`-a keçirdi, yəni işləməyən koda əl gəzdirildi.
`ruff` JS-ə baxmadığı üçün maşın qapısı belə şeyi prinsipcə tuta bilmir.

**8. B4-dən sonra yetim qalan CSS.**
`app/static/style.css:307-308` - `.stat.is-green` və `.stat.is-amber`.
Dörd stat kartının hamısı `is-accent` olduğu üçün bu iki qaydanın son
istifadəçisi getdi. (`.pill.is-green` və `.ribbon.is-amber` hələ də işlənir -
onlara toxunmaq olmaz.)

**9. `logs/notes.md`-də diff ilə uyğunlaşmayan üç iddia.**
- `:16` - «10 test (**4-ü** `node` ilə real icra)». Faylda `@needs_node` **5**
  dəfədir; `logs/review.md` düzgün «5 statik, 5 node» yazır.
- `:10` və `:13` - `storeColorSlot()` adlı funksiyanı silindi kimi göstərir.
  Belə ad nə `app.js`-də, nə `analytics.js`-də heç vaxt olmayıb. Real adlar:
  `storeColorVar()`, `storeColorIndex`, `colorFor()`, `warmColors()`.
- `:13` - «qoruyucu `typeof` yoxlaması SAXLANILDI». Əvvəlki `colorFor()`-da
  belə yoxlama yox idi; bu qol bu commitdə YENİ əlavə olunub.

**10. `analytics.js`-dəki qoruyucunun şərhi vəd etdiyinin əksini edir.**
Şərh: «yüklənmə sırası dəyişsə qrafik səssizcə yalan rəngə düşməsin».
Kod (`analytics.js:69-70`) isə `StoreColors` təyin olunmayıbsa `TOKENS.accent`
qaytarır - bu, bütün marketləri eyni rəngə salır, yəni məhz səssiz yalan rəng.
Üstəlik `app.js` eyni halda qoruyucusuz qırılır (`StoreColors.cssVar` TypeError).
İki fayl eyni riskə iki fərqli cavab verir; hansının doğru olduğu qərar tələb edir.
(`test_index_html_də_yüklənmə_sırası_doğrudur` sıranı qoruduğu üçün risk aşağıdır.)

**11. `README.md:331` köhnəldi, bu commitdə yenilənmədi.**
«Rəng market ADINA bağlanır və **reyestrdə saxlanılır**» - reyestr
(`storeColorIndex` Map) məhz bu commitdə silindi, indi hash + xətti sınaq var.
Cümlənin birinci yarısı ARTIQ doğrudur (əvvəl kod bunu etmirdi), ikinci yarısı
isə artıq yanlışdır. README-nin palitra cədvəli (`:324`, bənövşəyi = yalnız AI)
B1 düzəlişi ilə UYĞUNDUR - ziddiyyət yoxdur.

**12. B1 ilə eyni sinif defekt daha iki yerdə qalır.**
`--store-1: #0071E3` = `--accent: #0071E3`, `--store-4: #B45309` =
`--amber-ink: #B45309` - hərfbəhərf eyni hex. B1 yalnız `--store-2` ilə `--ai`
cütünü həll etdi. `logs/review.md` bunları XƏBƏRDARLIQ kimi qeydə alıb və qərar
qəsdən istifadəçiyə buraxılıb - amma «market rəngi status rəngi ilə
qarışmamalıdır» qaydası bu iki halda hələ də pozulur.

**13. 8 «keçildi» testinin hamısı özünü data-ya görə keçir.**
`test_mcp.py` (3), `test_voice.py` (3), `test_ui_contract.py` (2) - səbəblər:
«Bazada məhsul yoxdur» / «səbət boşdur». Baza boş olanda qapı yaşıl görünür,
MCP, səs və UI müqavilələri isə əslində yoxlanmır. Bu commitdən əvvəl də belə
idi (282/8, indi 292/8), yəni yeni problem deyil - amma qapıya arxalanarkən
yadda saxlanmalıdır.

---

### Yoxlandı, təmiz çıxdı

- **`ruff --fix`-in sildiyi 8 addan HƏR BİRİ ayrıca yoxlandı** - heç biri öz
  faylında istifadə olunmurdu və heç biri re-export kimi başqa moduldan
  çağırılmırdı:
  `ai/advisor.py` <- `strip_reasoning` (real istifadə: `app/api/basket.py:314`
  və `tests/test_sanitize.py`); `ai/cache.py` <- `Path`;
  `tests/test_analytics.py`, `tests/test_basket.py`, `tests/test_profile.py`
  <- `get_connection` (real istifadə: `ai/matcher.py:271`);
  `tests/test_matcher.py` <- `pytest` və `Candidate` (`Candidate` sinfi
  `ai/matcher.py:50`-də canlıdır və orada işlənir); `tools/scrape.py` <- boş
  f-string (həmin fayldakı `Path` importu `:20`-də işlənir, toxunulmayıb).
- **`E741` (`l` -> `line`, 3 yer)** - hər üçü comprehension dəyişənidir
  (`test_advisor.py:64`, `test_cleaner.py:99`, `test_ocr_upload.py:73`).
  Python 3-də comprehension dəyişəni öz sahəsindədir: kənar `line` adını nə
  kölgələyir, nə sızdırır. **Testlərin mənası dəyişməyib.**
- **`logs/commit-msg.txt` commit-ə düşüb** - texniki olaraq düzgündür
  (`.gitignore` `logs/`-u istisna etmir, fayl qəsdən əlavə olunub), amma
  məzmunca özünə istinad edir: «bu commit mesajını gatekeeper yazmalı idi...
  `logs/report.md` yazılmayıb». Bu hesabat həmin boşluğu bağladı, yəni
  `logs/commit-msg.txt` daxilindəki QEYD indi köhnəlmiş sayılır.
- `logs/review.md` diff ilə uyğundur: B1-B4 üçün «düzəldilib» yazılan hər sətir
  koddan təsdiqləndi (`--store-2: #4338CA`; tək mənbə; `.stat`-da `transform`
  yoxdur; dörd kart da `is-accent`).
- Yeni **xarici şəbəkə çağırışı yoxdur**. `robots.txt`, `REQUEST_DELAY_SECONDS`
  və `INGEST_API_KEY` məntiqinə **toxunulmayıb**.
- **Yeni `.env` açarı yoxdur**; `TESSERACT_CMD` və `TESSERACT_LANGS` artıq
  `.env.example:66-67`-dədir.
- **`try/except: pass` yoxdur**, `TODO` / `FIXME` / «hələlik» yoxdur.
  Qeyd: layihədə 20 `except Exception` var, amma heç biri `pass` deyil və heç
  biri bu commitdə dəyişməyib. Seçilmiş `select = ["E","F"]` dəsti `BLE001`-i
  kənarda qoyur, yəni qapı udulmuş xətaya prinsipcə baxmır.
- **Model çıxışı birbaşa HTML-ə düşmür**: market adları `app.js`-də `esc()`-dən
  keçir (`:57`, `:632`, `:652`), `StoreColors.cssVar()` isə yalnız
  `var(--store-N)` (N - rəqəm) qaytarır; inline `style`-a istifadəçi mətni
  girmir.

### 50-dən çox sətir dəyişən fayllar (səhər ayrıca oxunmalıdır)

| Fayl | Sətir | Növ |
|---|---|---|
| `logs/review.md` | +318 | sənəd (audit) |
| `tests/test_store_colors.py` | +231 | **yeni test - oxunmalıdır** |
| `app/static/store-colors.js` | +101 | **yeni məntiq - oxunmalıdır** |
| `logs/notes.md` | +76 | sənəd (9-cu bəndə bax) |

---

### Növbəti addım

`--store-1` = `--accent` və `--store-4` = `--amber-ink` eyniliyini bağlamaq
(B1-in yarımçıq qalan hissəsi) və eyni gedişlə 7+ market halını kilidləyən test
yazmaq - palitranın `--store-7`-yə genişləndiriləcəyi, yoxsa təkrar rəngin
qəbul ediləcəyi qərarı ilə birlikdə.
