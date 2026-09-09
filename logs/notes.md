# İcra qeydləri

## 2026-09-07 — B2: market rəngi ada bağlandı, toqquşma aradan qalxdı

### Nə dəyişdi

| Fayl | Dəyişiklik |
|---|---|
| `app/static/store-colors.js` | **YENİ.** `StoreColors` qlobalı: `note(names)`, `slot(name)`, `cssVar(name)`. Rəng məntiqinin yeganə mənbəyi. |
| `app/static/app.js:47-70` | `STORE_COLOR_COUNT`, `storeColorIndex` Map-i və `storeColorVar()` silindi; `storeChip` `StoreColors.cssVar()` çağırır. |
| `app/static/app.js:631, 651` | Bar avatarları `StoreColors.cssVar()`-a keçdi. |
| `app/static/app.js:738-742` | `loadCompare()` renderdən əvvəl `StoreColors.note(data.stores…)` çağırır. |
| `app/static/analytics.js:59-71` | `colorFor()` öz `storeColors` Map-i və `warmColors()` əvəzinə `StoreColors.slot()` çağırır; qoruyucu `typeof` yoxlaması BU DƏYİŞİKLİKDƏ əlavə olundu (əvvəl yox idi). |
| `app/static/analytics.js:118` | `drawHistory()` çəkilişdən əvvəl `StoreColors.note(data.stores)` çağırır. |
| `app/static/index.html:676-680` | `store-colors.js` `app.js` və `analytics.js`-dən əvvəl qoşuldu. |
| `tests/test_store_colors.py` | **YENİ.** 10 test (5-i `node` ilə real icra, `node` yoxdursa `skipif`). |

### Yanaşma

Hash xananı **təklif edir**, toqquşma **xətti sınaqla** (linear probing) həll
olunur; sınaq market adlarının **əlifba sırasında** aparılır. Əlifba backend-in
qaytardığı sıradan asılı olmadığı üçün nəticə giriş sırasından asılı deyil,
amma əlifbanın özü xana seçmir — yalnız toqquşmanı kəsir.

### Nəyi ölçdüm

Ölçmə: `node`, `app/static/store-colors.js` faylının özü işlədilib.

**1. Toqquşma — real 6 market adı** (`Test Market`, `Bravo`, `Araz`, `OBA`,
`Araz Market`, `Test Scrape Market`):

| | Fərqli xana |
|---|---|
| Təmiz djb2 hash (əvvəlki hal) | **3 / 6** — `Test Market`, `Bravo`, `OBA`, `Test Scrape Market` dördü də xana 5-də |
| Hash + probing (indiki hal) | **6 / 6** — {2, 5, 1, 0, 3, 4} |

**2. Toqquşma — təsadüfi adlar.** 5000 təsadüfi 6-lıq dəst (3–12 simvol,
latın + boşluq): təmiz hash-də **4929 dəstdə (98.6%)** ən azı bir toqquşma var.
Bu nəzəri gözləntiyə uyğundur (1 − 6!/6⁶ = 98.46%), yəni əvvəlki hal
«bəzən toqquşur» deyil, «demək olar həmişə toqquşur» idi.
Probing ilə yoxlanan bütün dəstlərdə toqquşma **0**.

**3. Sıra müstəqilliyi.** Eyni 6 ad 4 fərqli sıra ilə verildi (orijinal,
tərs, əlifba, qarışıq) → xana xəritəsi 4 halda da **eyni**.

**4. Dəst dəyişəndə sabitlik.** 5 marketdən 6-ya keçid (real adlar):
rəngi dəyişən market **0 / 5**. Səbəb: toqquşma olmadıqda hər ad öz hash
xanasını alır, qonşulardan asılı deyil.

**5. Test sayı.** `pytest -q`: əvvəl **282 keçdi / 8 keçildi**,
indi **292 keçdi / 8 keçildi** (51–56 san). Sınan test yoxdur.

**6. Testin özü işləyirmi?** Mutasiya yoxlaması: probing sətri müvəqqəti
silindi (təmiz hash-ə qayıdış) → `test_altı_market_altı_fərqli_xana_alır` və
`test_ixtiyari_altılıqlarda_da_toqquşma_yoxdur` **düşdü** (2 failed / 8 passed).
Fayl geri qaytarıldı. Yəni testlər regresiyanı həqiqətən tutur, sadəcə keçmir.

### Nəyə əmin deyiləm

- **Sabitlik zəmanətli deyil.** 4-cü ölçmə real adlar üçündür. Toqquşma
  zəncirinə düşən yeni market əlavə olunsa, həmin zəncirdəki marketlərin
  xanaları yenidən paylanır. Bunun nə qədər tez-tez baş verdiyini ölçmədim —
  ölçmək üçün real market əlavə tarixçəsi lazımdır, bizdə yoxdur.
- **7+ market.** 6 xanadan çox market olanda toqquşma riyazi olaraq
  qaçılmazdır; 7-ci ad öz hash xanasını (təkrar) alır. Uydurma 7-ci rəng
  çıxarmadım, amma bu halda leqenda yenə oxunmur. Palitranın genişləndirilməsi
  ayrı qərardır — `--store-7` token-i yoxdur.
- **Köhnəlmiş render.** `note()` renderdən əvvəl çağırılır, amma `app.js` və
  `analytics.js` ayrı-ayrı yüklənir. `analytics.js` yalnız qrafikdəki
  marketləri elan edirsə və orada `app.js`-in görmədiyi yeni ad varsa, artıq
  çəkilmiş cədvəl köhnə xanada qala bilər — növbəti `loadCompare()`-də düzəlir.
  Bunu brauzerdə ölçmədim, yalnız kod oxumaqla gördüm.
- **Brauzerdə vizual yoxlama yoxdur.** Testlər `node`-da işləyir; rənglərin
  ekranda həqiqətən fərqləndiyini (kontrast, yaxın tonlar) ölçmədim.
  `--store-1` = `--accent` və `--store-4` = `--amber-ink` uyğunluğu
  `logs/review.md`-də XƏBƏRDARLIQ kimi qalır — ona toxunmadım.

---

## 2026-09-08 — Addım 3: `price_snapshots` + market birləşdirmə

### Nə dəyişdi

| Fayl | Dəyişiklik |
|---|---|
| `app/db.py` | **`price_snapshots` cədvəli** + iki indeks; `products`-a `barcode` və `product_url`; `STORE_MERGES` + `_merge_duplicate_stores()`; `db_stats()`-a snapshot sayğacı |
| `ingestion/scraper.py` | Araz mənbəyinin adı `"Araz Market"` → `"Araz"` (yoxsa hər çəkiliş dublikatı yenidən yaradırdı) |
| `tests/test_snapshots.py` | **YENİ** — 11 test: gündəlik unikallıq, `source` qaydası, birləşdirmə |
| `tests/test_voice.py` | `test_axtarisda_geri_cekilme` öz datasını yaradır (aşağıya bax) |

### Nəyi ölçdüm

**1. Unikal indeks tapşırıqdakı formada İŞLƏMİRDİ.** Tapşırıq
`UNIQUE(product_id, store_id, source, observed_at)` yazırdı. `observed_at` tam
vaxt möhürü olduğu üçün eyni məhsul saat 09:00 və 18:30-da çəkiləndə **iki
sətir** yaranırdı — «hər gün bir sətir» qaydası kağız üzərində qalırdı.
Ölçmə: `date(observed_at)` üzrə ifadəli indekslə ikinci yazı `IntegrityError`
verir, ertəsi gün isə keçir. Mutasiya ilə təsdiq: indeksi tapşırıqdakı ilkin
variantına qaytardıqda `test_eyni_gun_ikinci_yazi_unikal_indekslə_tutulur`
**düşür** («DID NOT RAISE»). Yəni tapşırığın öz 9.1 testi ilkin sxemlə keçə
bilməzdi.

**2. `source` üçün CHECK əlavə olundu.** Tapşırıqda `-- 'site' | 'catalog'`
şərh idi. Şərh heç nə qorumur; üçüncü dəyər səssizcə yazılsaydı, həmin sətirlər
endirim yoxlamasının `source='site'` süzgəcindən kənarda qalar və bunu heç kim
görməzdi. Mutasiya ilə təsdiq: CHECK silinəndə müvafiq test düşür.

**3. Real bazada miqrasiya — data itkisi SIFIR.**

| | əvvəl | sonra |
|---|---|---|
| Araz (id 15) | 8 qiymət, 1 kataloq | **191 qiymət, 2 kataloq** |
| Araz Market (id 125) | 183 qiymət, 1 kataloq | **silindi** |
| cəmi qiymət | 551 | **551** |
| cəmi kataloq | 4 | **4** |

Ehtiyat nüsxə: `data/basketiq.db.bak-20260908-152906`.
UI-da yoxlanıldı: müqayisə cədvəlində artıq üç sütun var (Bravo, Araz, OBA),
boş «Araz Market — səbətdəki məhsulları satmır» sətri yoxdur, MARKET sayğacı
6 → 5.

**4. Testlər:** `pytest -q` **319 keçdi / 5 keçildi** (əvvəl 305/8), `ruff` təmiz.
Keçilən testlərin sayı azaldı, çünki 3 test artıq **həqiqətən işləyir** —
aşağıya bax.

### Yolda tapılan gizli problem

`tests/test_voice.py::test_axtarisda_geri_cekilme` adında «düyü» keçən məhsulun
bazada olmasını GÖZLƏYİRDİ, amma onu özü yaratmırdı. Boş test bazasında
`sebet_qorunur` fixture-u `pytest.skip()` etdiyi üçün test **heç vaxt
işləmirdi** — yaşıl görünürdü, halbuki heç nə yoxlamırdı. Mənim yeni testlərim
bazaya məhsul əlavə edən kimi fixture skip etməyi dayandırdı, test işə düşdü və
düşdü. Gözləntisi dəyişdirilmədi — test indi öz «düyü» məhsulunu yaradır.

Bu, `conftest.py`-ın sessiya boyu **tək baza** işlətməsinin nəticəsidir:
testlər bir-birinin datasını görür. Baza testdən-testə sıfırlansaydı belə gizli
asılılıq mümkün olmazdı — amma bu, ayrıca qərardır, bu addımda toxunmadım.

### Nəyə əmin deyiləm

- **Birləşdirmə siyahısı əl ilə doldurulur.** `Bravo` / `Bravo Express` kimi
  adları avtomatik birləşdirmək təhlükəlidir, ona görə oxşarlıq alqoritmi
  yazmadım. Yeni dublikat yaranarsa onu yalnız insan görəcək.
- **`observed_at` formatı sərbəstdir** — həm `2026-09-08`, həm
  `2026-09-08T09:00:00` qəbul olunur. İndeks hər ikisini düzgün oxuyur, amma
  yazan kodun hansını işlədəcəyi 4-cü addımda qərarlaşacaq.
- **`price_snapshots` hələ BOŞDUR.** Cədvəl və qaydalar hazırdır, doldurulması
  4-cü addımın işidir. İndiki `prices` cədvəli olduğu yerdə qalır — heç bir
  köhnə sətir köçürülmədi.

---

## 2026-09-08 — Bölmə 8: interfeys yenidən quruldu

### Nə dəyişdi

| Fayl | Dəyişiklik |
|---|---|
| `app/static/style.css` | trolley token-ləri (rəng, Poppins, 5px şəbəkə, 10px radius); ölü hero qaydaları silindi; `.answer`, `.basket-mini`, `.fold`, `.avatar.is-store`, `.fineprint` əlavə olundu; zebra zolağı silindi; mobil bloku |
| `app/static/index.html` | stat kartları admin panelinə köçdü; hero yenidən quruldu; 4 bölmə `<details>` oldu; dürüstlük qeydi; Poppins şrifti |
| `app/static/app.js` | `renderHero` yenidən yazıldı (cavab-əvvəl), `renderBasket` əlavə olundu, `storeAvatar` (dairə + hərf), guşə lenti silindi |
| `tests/test_ui_contract.py` | token gözləntiləri yeniləndi; `.hero-saving` müqayisədən çıxdı; **yeni** `test_ən_ucuz_siqnalı_rənglə_verilmir` |

### Nəyi ölçdüm

**1. Səhifə uzunluğu: 4918px → 1831px (−63%).** Səbəb: dörd stat kartı admin
panelinə köçdü və dörd bölmə (tarixçə, endirim, AI, profil) defolt bağlıdır.

**2. Kontrast — trolley palitrasının üç yeri AA-dan keçmirdi:**

| Cüt | Ölçmə | Həll |
|---|---|---|
| `text-muted #a9a9a9` kart fonunda | **2.11:1** | kiçik etiketlər `#525252`-yə (7.02:1) |
| `#4caf50` mətn kimi ağ fonda | **2.78:1** | `--ok-ink: #008000` (5.14:1) |
| **ağ** mətn yaşıl düymədə | **3.37:1** | qara mətn (6.24:1) — trolley-in öz komponent spesifikasiyası |

**3. Mobil 380px.** Əvvəl üfüqi daşma vardı (sənəd eni 632px, viewport 380px).
Səbəb yuxarı zolaq idi. Dar ekranda tab yazısı gizlənir (ikon qalır), stat
kartları tək sütuna düşür. İndi daşan element **yoxdur**.

**Ölçmə metodum əvvəlcə səhv idi:** `--window-size=380` verəndə Chrome-un
Windows-dakı minimum pəncərə eni real viewport-u **485px** edir. CDP
`Emulation.setDeviceMetricsOverride` ilə yenidən ölçdüm.

**4. Bağlı paneldə qrafik.** Risk: `<canvas>` sıfır ölçüdə çəkilə bilərdi.
Yoxlandı — panel açılanda kanvas 440×240 və 5480 boyalı piksel verir, yəni
qrafik düzgün çəkilir.

**5. Testlər:** `pytest -q` **320 keçdi / 5 keçildi**, `ruff` təmiz.

### Nəyə əmin deyiləm

- **«Şərtsiz cavab» hazırkı data ilə mümkün deyil.** Tapşırığın 8.2 bəndi
  «qalib market adı və cəm məbləğ» istəyir. Mövcud datada heç bir market
  səbətin hamısını satmır, ona görə ekranda yenə şərtli rəqəm (39.30 ₼ +
  «3 marketi gəzsəniz») görünür. Kod hər iki halı dəstəkləyir: tam səbəti
  satan market yaranan kimi ilk ekran avtomatik «Bravo — 34.10 ₼» formasına
  keçəcək. Bunu SÜNİ data ilə yoxlamadım.
- **Trolley ekran şəkilləri əlçatan deyildi** — skill qovluğunda yalnız
  `SKILL.md` var, `screens/` və `references/` yoxdur. Yəni yalnız sənədləşmiş
  token-lər tətbiq olunub; layout və animasiya detalları görülməyib.
- **Bölmə 8.4-dəki «~30% boşluq azalması» dəqiq ölçülmədi.** Bölmələr arası
  məsafə 24px → 15px (−37%), kart daxili boşluq 24px → 20px (−17%) oldu;
  ikincisi trolley spesifikasiyasının öz dəyəridir, ondan aşağı düşmədim.

---

## 2026-09-08 — Addım 9: README yeniləndi

### Nə dəyişdi

| Fayl | Dəyişiklik |
|---|---|
| `README.md` | dizayn dili bölməsi tam yenidən yazıldı (trolley sistemi, yeni rəng cədvəli, ölçülmüş kontrast); **yeni bölmə** «robots.txt oxuyucusu — `urllib`-dəki iki səhv»; **yeni bölmə** «Baza sxemi: `price_snapshots` və market birləşdirmə»; «İlk ekran: bir sual, bir cavab»; test sayları; status siyahısına 5 v2 bəndi |
| `app/static/analytics.js` | **köhnəlmiş token adları düzəldildi** (aşağıya bax) |
| `app/static/app.js` | «yaşıl fon» şərhi reallığa uyğunlaşdırıldı |
| `tests/test_ui_contract.py` | **yeni** `test_js_in_oxuduğu_hər_token_root_da_var` |

### Yolda tapılan səssiz sınma

`analytics.js` qrafik rənglərini CSS-dən oxuyur:
`cssVar("--green", "#34C759")`. Trolley palitrasına keçəndə həmin token
`--ok` oldu, amma JS yenilənmədi — `getComputedStyle` boş sətir qaytardı və kod
**səssizcə köhnə hardcode rəngə düşdü**. Qrafik yenə çəkilirdi, sadəcə səhifə
ilə fərqli rəngdə: nə xəta, nə xəbərdarlıq, nə də düşən test.

Bu, mənim öz dəyişikliyimin yaratdığı səhv idi — token adını dəyişəndə JS
tərəfini yoxlamamışdım.

Düzəliş: `--ok` / `--info` adları, ehtiyat dəyərlər də palitradan.
Test: JS-in `cssVar()` ilə soruşduğu hər token `:root`-da olmalıdır.
Mutasiya ilə təsdiq: adı `--green`-ə qaytardıqda test düşür
(«analytics.js olmayan token oxuyur: ['--green']»).

### README-də düzəldilən digər səhv

Axın sxemində sətir zədəli idi: `zibil sətirlərin atılm11` + növbəti sətirdə
`ası`. Eyni sxemdə model «Qwen (Ollama)» yazılırdı — halbuki əsas provayder
Claude-dur, Ollama ehtiyatdır.

### Testlər

`pytest -q` → **321 keçdi / 5 keçildi**, `ruff` təmiz.

### Nəyə əmin deyiləm

- README **730+ sətirdir** və hamısını sətir-sətir yoxlamadım. Yenilədiyim
  yerlər: mənbə cədvəli, dizayn dili, ilk ekran, robots, baza sxemi, test
  sayları, status. Köhnə bölmələrdə (MCP, n8n, səs, deployment) v2-dən sonra
  yanlışlaşan iddia qalmış ola bilər.
- Status siyahısında «v2 — mağaza qatı» bəndi **açıq** (`[ ]`) qaldı, çünki
  mənbə tapılmadı. Bu, tamamlanmamış iş kimi görünür — real vəziyyət elə odur.

---

## 2026-09-09 — v3: trolley strukturu, məhsul şəkilləri, axtarış səhifəsi

İstinad sayta (trolley.co.uk) yenidən baxıldı və struktur ona uyğunlaşdırıldı.
**Alış-veriş yoxdur** — nə səbətə əlavə düyməsi, nə checkout, nə ödəniş.
Məqsəd yalnız qiymət göstərmək və müqayisə etməkdir.

### Nə dəyişdi

| Fayl | Dəyişiklik |
|---|---|
| `tools/purge_store.py` | **yeni** — market + qiymətləri + yetim məhsulları silir, əvvəl ehtiyat nüsxə götürür |
| `ingestion/images.py` | **yeni** — kataloq səhifəsindən məhsulun xanasını kəsir |
| `tools/build_images.py` | **yeni** — CLI: kataloqları gəzir, şəkilləri yazır, hesabat çap edir |
| `app/db.py` | `products.image_path` sütunu (miqrasiya) |
| `app/static/search.html` / `search.js` | **yeni** `/search` səhifəsi: şəkilli kart şəbəkəsi + filtrlər |
| `app/catalog.py` | `search()` + `facets` (filtr menyusu real datadan qurulur) |
| `app/static/index.html` / `deals.js` | axtarış paneli yuxarı, endirimlər kart şəbəkəsi deyil **nömrələnmiş siyahı** |
| `app/static/product.js` / `product.html` | iki sütun: solda kimlik + böyük şəkil, sağda qiymətlər; «Bugünkü qiymət» zolağı |
| `tests/test_ui_contract.py` | **yeni** `test_hər_səhifə_müqavilədə_qeydiyyatdadır` |

**OBA tamamilə silindi** — kod, testlər, sənədlər və baza. Uydurma slug testlərdə
«kənar-market» adlandırıldı; `grep -i oba` bütün layihədə boş qayıdır.

### Məhsul şəkilləri: niyə kəsirik, endirmirik

Trolley şəkilləri marketin onlayn mağazasından götürür. Bizdə belə mənbə
**yoxdur** (`logs/sources.md`-də ölçülüb). Yeganə real mənbə həftəlik kataloq
şəklidir — məhsulun fotosu **onun içindədir**.

`layout.py` onsuz da hər məhsulun qiymət qutusunu tapır. Kataloq kartlar
şəbəkəsi olduğu üçün iki qonşu qiymət qutusu arasındakı məsafə xananın
ölçüsünü verir; şəkil qiymətin üstündədir, deməli xana = qiymət qutusunun
mərkəzindən yuxarı bir sıra addımı, yanlara yarım sütun addımı.

Məhsulu şəklə `prices.raw_line` bağlayır. **Yalnız mətn oxşarlığı səhvə
aparırdı** — düşbərənin yerinə su qabı düşürdü. Namizədləri qiymət daraldır,
hədd `MATCH_THRESHOLD = 0.55`, iki namizəd yaxın olanda şəkil **verilmir**.
Səhv şəkil placeholder-dən pisdir: istifadəçi başqa məhsulu görüb qiyməti ona
aid sayır.

### Nəyi ölçdüm

**1. Şəkil əhatəsi (bazadan, 2026-09-09):** 194 məhsuldan **73-ünün** şəkli var
(≈38%). Hamısı Araz kataloqlarındandır. **Bravo-nun 8 məhsulunun heç birində
şəkil yoxdur** — Bravo datası kataloq səhifəsindən gəlmir, deməli kəsiləcək
kadr da yoxdur. Qalan məhsullar neytral placeholder alır.

**2. Testlər:** `pytest -q` → **366 keçdi / 2 atlandı**, `ruff` təmiz.

**3. Yeni test real səhvdən çıxdı.** `search.html` yaradıldı, səhifə siyahısı
əl ilə yazıldığı üçün yenilənmədi və **yeni səhifə heç bir testə düşmürdü** —
bütün testlər isə yaşıl keçirdi. İndi siyahı fayl sistemi ilə tutuşdurulur;
ikon yoxlaması da qovluqdan oxuyur, siyahıdan yox.

### Yolda tapılan mühit tələsi

Bu worktree-də `pytest` **8 testdə düşürdü**:
`TesseractNotFoundError: tesseract is not installed`. Səbəb kod deyil —
`.env` fayl gitignore-dadır, yəni worktree-yə köçmür, `TESSERACT_CMD` isə boş
qalır. `.env` köçürüldükdən sonra 366 test keçdi.

Diqqətçəkən tərəfi: şrift tapılmayanda testlər **ötürülür**
(`pytest.skip("TrueType şrift tapılmadı")`), tesseract tapılmayanda isə xam
istisna ilə **düşür**. Eyni kateqoriyalı mühit boşluğu iki cür davranır.

### Nəyə əmin deyiləm

- **Şəkil bağlantısı yoxlanmayıb, ölçülüb.** 73 şəklin hər birinə baxıb
  «bu, doğrudan həmin məhsuldur» demədim. 0.55 həddi zəif uyğunluqları atır,
  amma **yanlış-müsbət sayı bilinmir**.
  → **Sonradan ölçüldü (2026-09-09, aşağıdakı bölmə): 73-dən 21-i səhvdir.**
- **Şəkillər repo-ya düşmür** (`.gitignore`). Təmiz klonda bütün məhsullar
  placeholder ilə görünəcək; şəkilləri `tools/build_images.py` yenidən qurur.
- **`/search` yalnız mövcud datada sınandı** — 194 məhsul. Səhifələmə davranışı
  (böyük nəticə dəsti) real datada yoxlanmayıb.

---

## 2026-09-09 — Şəkillərin yoxlanması: 73-dən 21-i səhvdir

Əvvəlki bölmədə «yanlış-müsbət sayı bilinmir» yazmışdım. İndi bilinir.

### Metod

73 şəklin hamısına gözlə baxıldı. Yoxlama mümkündür, çünki kəsilmiş kadr
kartın **öz yazısını** (brend + ad + qramaj) da içinə alır — bazadakı ad kadrın
öz etiketi ilə tutuşdurulur, üçüncü mənbə lazım deyil. 12-lik vərəqlər qurulub
hər xananın altına `#id ad [brend] ölçü` yazıldı. Təkrarlanan kadrlar ayrıca
**SHA-256** ilə sayıldı — göz aldana bilər, hash yox.

### Nəticə

| | Say | Pay |
|---|---|---|
| Doğru | 48 | 66% |
| **Səhv** | **21** | **29%** |
| Şübhəli (növ uyğun, brend yox) | 4 | 5% |

Tam siyahı və hər səhvin nə olduğu: `logs/image-check.md`.

### Səbəb koddadır, dataya aid deyil

**1. Bir kart bir neçə məhsula verilir.** `tools/build_images.py` hər məhsul
üçün ən yaxşı kartı ayrıca seçir, amma seçilmiş kartı siyahıdan **çıxarmır**.
Hash göstərdi: 73 fayldan yalnız **63-ü unikal**, 20 məhsul 10 kartı bölüşür.
Uyğunlaşma bir-birə olmalı ikən bir-çoxadır.

**2. Qiymət açarı ehtiyac olan anda sönür.** Şərh «QİYMƏT BİRİNCİ AÇARDIR»
deyir, kod isə `pool = priced or cards` yazır — qiyməti uyğun kart yoxdursa
süzgəc **tamamilə düşür** və qərarı yalnız mətn verir. «Sosis → Pringles»,
«it yemi → plastilin» buradan gəlir.

**3. `raw_line` çox vaxt bir neçə kartın mətnidir** (#1921: `Penstore Karandaş
12 rəng Penstore Qayçı ASH Su qabi 5.79`). Həddi qaldırmaq bunu düzəltmir —
problem hədd deyil, müqayisə olunan mətndir.

### İkinci qüsur: kadr sürüşür

Uyğunlaşma doğru olanda belə sol kənar kəsilir (brend yarımçıq: «omaster»,
«ickers/Bounty», «aello», «ineken»), ən azı 6 kadrda isə (#1944, #1945, #1973,
#1974, #1976, #1977) məhsulun fotosu kadrda demək olar yoxdur — yalnız qiymət
qutusu var. `is_blank()` bunu tuta bilmir: mətn və qırmızı qutu dispersiyanı
yüksək saxlayır.

### Nəyə əmin deyiləm

- **Şübhəli 4 hökm mənimdir.** #1935 (Korovka: brend uyğun, növ yox) və #1952
  (qəhvə: növ uyğun, brend yox) «səhv» sayılsaydı, nisbət 29%-dən 34%-ə
  qalxardı. Sərhəd qərarı mənimdir, ölçmə deyil.
- **Yalnız Araz kataloqları yoxlandı** — başqa mənbədə kart quruluşu fərqli
  olsa, nisbət də fərqli olacaq.
- **Kod dəyişdirilmədi.** Bu, ölçmədir; düzəliş ayrı qərardır.


---

## 2026-09-09 — Düzəliş: uyğunlaşma bir-birə oldu, qiymət məcburi

Ölçmədə tapılan iki qüsur düzəldildi. **Sonra eyni metodla yenidən sayıldı** —
düzəlişin işlədiyini iddia etmək kifayət deyil.

### Nə dəyişdi

| Fayl | Dəyişiklik |
|---|---|
| `ingestion/images.py` | **yeni** `assign_cards()` — uyğunlaşdırma məntiqi buraya çıxarıldı və bir-birə edildi; `better_reason()`; `Assignment`; `AMBIGUITY_GAP` |
| `tools/build_images.py` | döngə `assign_cards()`-a bağlandı; `CropReport.skipped` artıq **səbəbə görə** ayrılır |
| `tests/test_images.py` | **yeni fayl, 11 test** |

**1. Uyğunlaşma bir-birədir.** Kart tutulandan sonra siyahıdan çıxır; məhsul da
yalnız bir kart alır (eyni kataloqda bir neçə qiymət sətri olan 3 məhsul var —
onlar iki kart qazanıb ikinci faylı birincinin üstünə yazırdı, **səssizcə**,
çünki fayl adı `p<id>.jpg`-dir). Qərar bazadakı sıra ilə deyil, **xal sırası**
ilə verilir: əvvəl bütün iddialar hesablanır, sonra ən yüksəkdən paylanır.

**2. Qiymət məcburidir.** `pool = priced or cards` silindi. Qiyməti uyğun kart
yoxdursa məhsul placeholder alır.

**3. Atılma səbəbi hesabatda görünür.** «30 məhsul şəkilsiz qaldı» faydasızdır;
indi yazılır: `qiymət yoxdur: 72, zəif: 45, kart tutulub: 1`. Səbəb yalnız
**sonda**, şəkilsiz qalanlar üzrə sayılır — əvvəl hər səhifə eyni məhsulu
yenidən sayardı.

### Nəticə (eyni metod, gözlə sayılıb)

| | Əvvəl | Sonra |
|---|---|---|
| Şəkil | 73 | 62 |
| Doğru | 48 (66%) | **48 (77%)** |
| Səhv | **21 (29%)** | **10 (16%)** |
| Unikal kadr | 63/73 | **62/62** |

Doğru şəkillərin sayı **dəyişmədi**, səhvlər iki dəfədən çox azaldı. SHA-256 ilə
fayl-fayl müqayisə: 11 məhsul şəkilsiz qaldı (9-u səhv idi, 2-si doğru),
6 məhsul başqa kart aldı və **hamısı düzəldi** (#1954 flomaster → Tess çayı,
#1929 Damak → Ulduz Start, #1941 və #1975 təkrar kadrdan qurtuldu).

### Testlər əvvəl YOX İDİ — səhv ona görə keçdi

`assign_cards()`-ın 11 testi yazıldı. İkisi mutasiya ilə təsdiqləndi:
düzəlişi geri qaytaranda **hər ikisi düşür**

```
kart tutulmuş sayılmır  -> 1 failed, 9 passed
qiymət açarı sönür       -> 1 failed, 9 passed
```

`pytest -q` → **377 keçir, 2 atlanır**, ruff təmiz.

### Nəyə əmin deyiləm

- **Qalan 10 səhv şəkil qatına aid deyil.** Orada səhv kartın qiyməti eynidir
  və `raw_line` həmin kartın mətnini həqiqətən saxlayır (#1921: `Penstore
  Karandaş 12 rəng Penstore Qayçı ASH Su qabi 5.79`). Uyğunlaşma öz qaydası ilə
  düzgün işləyir; səhv daha erkəndə — `ingestion/layout.py` üç kartın yazısını
  bir sətrə yığır. Bunu şəkil qatında həll etmək mümkün deyil.
- **İki doğru şəkil itdi** (#1922 şokolad batonçuğu, #1958 kukuruz). Qiymət
  şərtinin sərtləşməsi onları da kəsdi — əhatə ilə dürüstlük arasında qəsdən
  edilmiş mübadilədir.
- **Kadrın sürüşməsinə toxunulmadı** — sol kənar hələ də kəsilir.

---

## 2026-09-09 — `layout.py`: sətirlərin qarışması

Şəkil səhvlərinin «3-cü səbəbi» həll olundu.

### Səbəb

Səhifədə **175 qırmızı qutu**, amma yalnız **102-sinin qiyməti oxunur**
(Araz-da qiymət ikimərtəbəlidir). Qiyməti oxunmayan qutu şəbəkədən tamamilə
çıxırdı; söz isə «özündən sonrakı ilk lövbərə» bağlanır — deməli o kartın
sözləri qonşuya axırdı.

### Nə dəyişdi

| Fayl | Dəyişiklik |
|---|---|
| `ingestion/layout.py` | şəbəkə **bütün** qırmızı qutulardan qurulur; **yeni** `_grid_landmarks()` (ölçü süzgəci); `_first_at_or_after()` sənədləşdirildi |
| `tests/test_layout.py` | **yeni** 2 test (biri OCR-lı uçdan-uca, biri vahid) |

Qiymətsiz qutu kart yaratmır, amma **öz xanasını sahiblənir** — sözləri
qonşuya getmir, atılır.

### Sınadım, ÖLÇDÜM, ATDIM

İlk variantım sözün lövbərdən məsafəsini `_grid_step()` ilə məhdudlaşdırırdı.
Səhv idi: **`_grid_step()` kartın eni deyil** — qonşu qiymət qutuları
arasındakı median məsafədir və qutular yan-yana düşəndə kiçilir. 6-cı səhifədə
ölçdüm: `col=112`, halbuki kart ~250 pikseldir. Nəticə: kartın ÖZ sözləri
kəsilirdi — «Nestle Damak Şokolad» → «Şokolad», «Lotte Choco Pie» → «Lotte Pie».

Fərziyyə ilə davam etsəydim bunu görməzdim; iki dəyişikliyi **ayrı-ayrı**
ölçdüm və günahkarın hansı olduğu ordan çıxdı.

### Ölçmə (20 səhifə, 102 kart)

| | Əvvəl | Sonra |
|---|---|---|
| 12 sözdən uzun kart | 6 | **1** |
| Ən uzun kart | 23 söz | 20 söz |
| Boş kart | 14 | 15 |

```
«Penstore Karandaş 12 rəng Penstore Qayçı ASH Su qabi» → «ASH Su qabi»
«Chupa Chups q 25% 18% Mentos Saqqız 15.5 q»           → «Mentos Saqqız 15.5 q»
«Sf Nescafe Qəhvə 145q Starbucks Premium qəhvə»        → «Sf Nescafe Qəhvə 145q»
```

### Uçdan-uca nəticə İKİ TƏRƏFLİDİR

| | Əvvəl | Sonra |
|---|---|---|
| Şəkil | 62 | 51 |
| Doğru | 48 (77%) | **42 (82%)** |
| Səhv | 10 (16%) | **6 (12%)** |

Səhv nisbəti düşdü, **amma 6 doğru şəkil də itdi.** Səbəb: uyğunlaşdırma
saxlanılmış `raw_line` ilə **canlı** kart mətnini tutuşdurur; `raw_line` köhnə
layout ilə yazılıb və qarışıqdır. Kart mətni təmizləndikcə oxşarlıq düşür və
0.55 həddini keçmir.

### Nəyə əmin deyiləm

- **Bu düzəlişin tam faydası mövcud bazada GÖRÜNMÜR.** Onu görmək üçün kataloq
  yenidən emal olunmalıdır (`raw_line` yenidən yazılsın) — bu, LLM zəncirini
  işə salır və məhsul/qiymət sətirlərini yenidən qurur. Ayrıca qərardır,
  etmədim.
- **10-cu səhifədə 3 kart mətnini itirdi.** Onların mətni onsuz da qarışıq idi
  («Marsianka 17.00 49 “1 32% sə) Candy G. Frully Qlazurlu»), amma indi
  ümumiyyətlə mətn yoxdur — bu, itkidir.
- **Bir qarışıq kart qaldı** (14-cü səhifə, «Şirniyyat boşqabı» + «Nescafe
  Gold»). Orada qonşu kartın qırmızı qutusu ümumiyyətlə tapılmır, yəni xana
  sahibi yoxdur.
- **Ölçü süzgəcinin sərhədləri (0.6–1.6) bir kataloqda seçilib.** Başqa
  dizaynda nişanla qiymət qutusunun nisbəti fərqli ola bilər.

---

## 2026-09-09 — Kataloq yenidən emal olundu + yetimlər silindi

Layout düzəlişinin tam faydası görünmürdü, çünki `raw_line` köhnə layout ilə
yazılmışdı. Kataloq bütöv yenidən emal olundu: OCR → LLM → baza.

### Yolda MƏNİM səhvim (və onun tapılması)

İlk yenidən emalı `OCR_MAX_PAGES=20` ilə işlətdim. Nəticə çökdü: Araz
188 → 69 məhsul, qiymət 183 → 62. Bunu «layout düzəlişi datanı qırdı» kimi
oxumaq asan olardı — və səhv olardı.

Ölçdüm: köhnə və yeni kart mətnlərini **eyni təmizləyicidən** keçirdim →
**83 sətir vs 78 sətir**, yəni layout cəmi 5 sətir aparıb. Əsl səbəb köhnə
mətnin **54 səhifədən** gəlməsi idi. 54 səhifə ilə təkrarladım: mətn yenə
**478 sətir**, tam köhnə fayl kimi.

**Dərs:** rəqəm düşəndə ilk şübhəli ən son dəyişiklik olur, amma çox vaxt
günahkar o deyil. Fərziyyəni yox, hər amili ayrıca ölçmək lazımdır.

### Nə edildi

| Addım | Nəticə |
|---|---|
| OCR (54 səhifə, düzəlmiş layout) | 271 kart, 478 sətir, 12 581 simvol |
| LLM zənciri | 214 sətir emal, 177 məhsul yazıldı, 37 atıldı (141 keşdən, 73 modeldən, 0 uğursuz, 109 san) |
| Şəkillərin qurulması | 60 şəkil (uyğunluq 60, atıldı: qiymət yoxdur 66, zəif 47, kart tutulub 2) |
| Yetimlərin silinməsi | 234 → 188 məhsul, yetim 0 |

### Yekun ölçmə (60 şəklin hamısına gözlə baxıldı)

| | Başlanğıc | Uyğunlaşma | + layout | + yenidən emal |
|---|---|---|---|---|
| Şəkil | 73 | 62 | 51 | **60** |
| Doğru | 48 (66%) | 48 (77%) | 42 (82%) | **50 (83%)** |
| **Səhv** | **21 (29%)** | 10 (16%) | 6 (12%) | **6 (10%)** |
| Unikal kadr | 63/73 | 62/62 | 51/51 | **60/60** |

Araz məhsulu **183**, qiymət sətri **177** — yəni əhatə bərpa olundu və səhv
üç dəfə azaldı.

Kartlar öz məhsullarını tapdı: «ASH Su qabı» → #2571 su qabı (əvvəl
«karandaş»), «Bizim Tarla ərik/şaftalı cemi» → #2605 (əvvəl «şokolad
pastası»), «Yemək qabı və termos dəsti» → #2564 termos (əvvəl heç kimə).

### Yeni alət: `tools/purge_orphans.py`

`save_products()` kataloqun qiymətlərini silib yenidən yazır, `products`
cədvəlinə toxunmur — ona görə əvvəlki emalın məhsulu qiymətsiz qalır. Alət
onları göstərir (quru qaçış) və `--apply` ilə silir; ehtiyat nüsxə həmişə
götürülür, səbət sətri və şəkil faylı da təmizlənir.

4 test yazıldı. Mutasiya ilə təsdiqləndi: silmə şərtini götürəndə 3 test düşür.

### Nəyə əmin deyiləm

- **Qalan 6 səhv artıq şəkil səhvi deyil.** Kart doğru tapılır, LLM isə
  sətirdən yanlış ad çıxarır: kart «Süfrə Sous» deyir, bazadakı ad «duz».
  Növbəti addım şəkil qatında yox, **atribut çıxarmadadır**.
- **Şəkil yalnız ilk 20 səhifədən kəsilir** (`build_images` 20 səhifə oxuyur),
  məhsullar isə 54 səhifədən gəlir. 188 məhsuldan 60-ının şəkli olmasının
  səbəbi budur — 54 səhifənin hamısını kəsmək sınanmadı.
- **Şübhəli 4 hökm mənimdir** (#1935, #1952, #1956, #2612): növ uyğundur,
  brend və ya ölçü yox. «Səhv» sayılsaydılar nisbət 10%-dən 17%-ə qalxardı.
