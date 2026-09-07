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
