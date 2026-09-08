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
