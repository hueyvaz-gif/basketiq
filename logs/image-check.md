# Məhsul şəkillərinin yoxlanması (2026-09-09)

`ingestion/images.py` kataloq səhifəsindən kartın xanasını kəsir və məhsula
bağlayır. Kod «zəif uyğunluq atılır» deyirdi, amma **yanlış-müsbət sayı heç vaxt
ölçülməmişdi**. Bu sənəd həmin ölçmədir.

## Metod

73 şəklin hamısına **gözlə** baxıldı. Yoxlama mümkündür, çünki kəsilmiş kadr
kartın **öz yazısını** (brend + məhsul adı + qramaj) da içinə alır — yəni
bazadakı ad kadrın öz etiketi ilə birbaşa tutuşdurulur, üçüncü mənbəyə ehtiyac
yoxdur. Şəkillər 12-lik vərəqlərə yığıldı, hər xananın altına `#id ad [brend]
ölçü` yazıldı.

Təkrarlanan kadrlar ayrıca **SHA-256 ilə** sayıldı — göz aldana bilər, hash yox.

## Nəticə

| | Say | Pay |
|---|---|---|
| **Doğru** — kadrın etiketi bazadakı adla üst-üstə düşür | 48 | 66% |
| **Səhv** — kadr başqa məhsulundur | **21** | **29%** |
| **Şübhəli** — növ uyğundur, brend yox (və ya əksi) | 4 | 5% |
| Cəmi | 73 | |

**Hər üç şəkildən biri səhv məhsulu göstərir.** Qiymət müqayisəsi tətbiqində bu,
sadəcə kosmetik qüsur deyil: istifadəçi şəkli görüb qiyməti ona aid sayır.

## Təkrarlanan kadrlar (hash ilə təsdiqlənib)

73 fayldan **63-ü unikal**; 10 kadr iki-iki paylaşılıb, yəni **20 məhsul**
10 kartı bölüşür. Bir kart bir məhsuldur — deməli hər cütdə **ən azı biri
səhvdir**:

```
#1915 flomaster          ↔ #1954 çay [Tess]
#1918 su qabı            ↔ #1948 saxlama qabı
#1922 şokolad batonçuğu  ↔ #1941 şokolad [Snickers/Bounty/Mars/Twix]
#1924 kreker [Tuc]       ↔ #2474 paltar yuyucu vasitə [Ariel]
#1925 şokolad [Damak]    ↔ #1929 şokolad [Ulduz Start]
#1930 peçenye [Ura]      ↔ #2554 sane [Milla]
#1945 günəbaxan yağı     ↔ #2519 günəbaxan [Tac]
#1967 cola [Berg]        ↔ #1975 soyuq çay [L.A tea]
#2381 qaymaq [ETTA]      ↔ #2463 it yemi [Qav]
#2508 sitrus             ↔ #2526 sosis
```

## Səhv şəkillərin siyahısı

| Məhsul (bazada) | Kadr əslində nədir |
|---|---|
| #1921 karandaş [Penstore] 12 əd | ASH Su qabı 5.79 |
| #1927 armudu stəkan 6 əd | Canpa Marmelad 450 q |
| #1929 şokolad [Ulduz Start] | Damak Şokolad 60 q *(təkrar)* |
| #1939 dondurma [Zabava] | Zabava **Kreker** kq |
| #1948 saxlama qabı | ASH Su qabı 3.99 *(təkrar)* |
| #1950 cips | ASH Penal / Penstore Karandaş |
| #1953 şirniyyat boşqabı | Tac Kəllə qənd 1 kq |
| #1954 çay [Tess] 20 əd | Flomaster 12 ədədli *(təkrar)* |
| #1956 şokolad [Nestle] 190 q | Aquşa Meyvə püresi 90 q |
| #1959 şokolad pastası [Seyidoğlu] | Bizim Tarla ərik/şaftalı cemi 300 q |
| #1966 ketçup [Bostan] 350 q | Bostan **xiyar turşusu** 700 q |
| #1967 cola [Berg] 500 ml | İce Tea Soyuq çay 500 ml |
| #1968 qazlı içki [Pepsi] | Slavyanka Limonad 1.5 L |
| #1969 sərinləşdirici içki [Bizon] 450 ml | Tac Cola/Orange 2 L |
| #2381 qaymaq [ETTA] | ETTA **Plastilin** 5 rəng |
| #2463 it yemi [Qav] | ETTA Plastilin 5 rəng *(təkrar)* |
| #2474 paltar yuyucu vasitə [Ariel] | Tuc Kreker 100 q *(təkrar)* |
| #2508 sitrus | Pringles Çips 40 q |
| #2519 günəbaxan [Tac] 1 kq | Zateya günəbaxan **yağı** 1.8 L *(təkrar)* |
| #2526 sosis | Pringles Çips 40 q *(təkrar)* |
| #2554 sane [Milla] 250 q | Ura peçenye 240 q *(təkrar)* |

**Şübhəli 4-ü:** #1935 süd məhsulu [Korovka] → kadr «Korovka konfet» (brend
uyğun, növ yox); #1942 qlazurlu kəsmik [Marsianka] → kadr «S. Frully peçenye»;
#1952 qəhvə [Nescafe] → kadr Starbucks/Jardin qəhvəsi (növ uyğun, brend yox);
#1965 tomat pastası [Bizim] → kadr «Final tomat pastası» (növ uyğun, brend yox).

## Səbəb — koddadır, dataya aid deyil

**1. Bir kart bir neçə məhsula verilə bilir.** `tools/build_images.py`-də hər
məhsul üçün ən yaxşı kart ayrıca seçilir, amma **seçilmiş kart siyahıdan
çıxarılmır**. İki məhsul eyni kartı «qazana» bilər — 10 təkrar qrupu məhz
budur. Uyğunlaşma bir-birə olmalı ikən bir-çoxadır.

**2. Qiymət açarı səssizcə itir.** Kod deyir «QİYMƏT BİRİNCİ AÇARDIR», amma:

```python
pool = priced or cards      # qiyməti uyğun kart yoxdursa -> BÜTÜN kartlar
```

Səhifədə həmin qiymətli kart tapılmayanda süzgəc tamamilə düşür və qərarı
yalnız mətn oxşarlığı verir. «Sosis → Pringles», «it yemi → plastilin» kimi
nəticələr buradan gəlir — qorunma məhz ehtiyac olan anda söndürülür.

**3. `raw_line` çox vaxt bir neçə məhsulun mətnidir.** Məsələn #1921-in xam
sətri: `Penstore Karandaş 12 rəng Penstore Qayçı ASH Su qabi 5.79` — üç ayrı
kartın yazısı bir sətirdə. Belə sətirlə hesablanan oxşarlıq nəyi ölçdüyünü özü
də bilmir. Hədd 0.55-i qaldırmaq bunu düzəltmir, çünki problem hədd deyil,
müqayisə olunan mətndir.

## İkinci qüsur: kadr sürüşür

Uyğunlaşma DOĞRU olanda belə çərçivə çox vaxt yerində deyil:

- Sol kənar kəsilir — brend adı yarımçıq qalır: «omaster» (Flomaster),
  «ickers/Bounty» (Snickers), «aello» (Raffaello), «ineken» (Heineken).
- Ən azı **6 kadrda** (#1944, #1945, #1973, #1974, #1976, #1977) məhsulun
  fotosu ya tamamilə kənarda qalıb, ya da nazik zolaq kimi görünür — kadrda
  faktiki olaraq yalnız qiymət qutusu var.

`is_blank()` bunları tuta bilmir: kadrda mətn və qırmızı qiymət qutusu olduğu
üçün rəng dispersiyası yüksəkdir, yəni «boş deyil» sayılır.

---

# Düzəlişdən sonra (eyni gün, eyni metod)

İki qüsur düzəldildi: (1) uyğunlaşma **bir-birə** oldu — kart da, məhsul da
yalnız bir dəfə seçilir və qərar bazadakı sıra ilə deyil, **xal sırası** ilə
verilir; (2) qiymət uyğunluğu **məcburi** oldu (`pool = priced or cards`
silindi). Sonra şəkillər sıfırdan qurulub **yenidən gözlə sayıldı**.

| | Əvvəl | Sonra |
|---|---|---|
| Şəkil sayı | 73 | **62** |
| Doğru | 48 (66%) | **48 (77%)** |
| **Səhv** | **21 (29%)** | **10 (16%)** |
| Şübhəli | 4 (5%) | 4 (6%) |
| Unikal kadr | 63 / 73 | **62 / 62** |

**Doğru şəkillərin sayı dəyişmədi (48), səhvlərin sayı isə iki dəfədən çox
azaldı.** Yəni itirilən 11 şəklin 9-u onsuz da səhv idi. Fayl-fayl müqayisə
(SHA-256) bunu təsdiqləyir:

- **11 məhsul şəkilsiz qaldı:** #1948, #1953, #1967, #2463, #2474, #2508,
  #2519, #2526, #2554 (hamısı **səhv** idi) və #1922, #1958 (doğru idi).
- **6 məhsul BAŞQA kart aldı və hamısı düzəldi:** #1929 (Damak → Ulduz Start),
  #1941 (Snickers təkrarı → Mini şokolad), #1954 (flomaster → **Tess çayı**),
  #1975 (Ice Tea təkrarı → I'm tea), #1937, #1978.
- 56 məhsulun kadrı dəyişmədi.

## Qalan 10 səhv — üçüncü səbəbdəndir

Qalanlar təsadüf deyil: onlarda səhv kartın qiyməti **eynidir** və `raw_line`
həmin kartın mətnini **həqiqətən içində saxlayır**. Nümunə #1921:

```
raw_line: «Penstore Karandaş 12 rəng Penstore Qayçı ASH Su qabi 5.79»
kart:     «ASH Su qabı 5.79»          ← qiymət eyni, mətn sətrin içindədir
```

Yəni uyğunlaşma öz qaydası ilə **düzgün işləyir**; səhv daha erkəndədir —
üç ayrı kartın yazısı bir məhsul sətrinə yığılıb. Bunu şəkil qatında həll
etmək mümkün deyil, `ingestion/layout.py` sətri düzgün bölməlidir.

Qalan 10: #1921, #1927, #1939, #1950, #1956, #1959, #1966, #1968, #1969, #2381.

## Nə edilmədi

**Kadrın sürüşməsi** (sol kənarın kəsilməsi, fotonun kadrdan çıxması)
toxunulmadı — o, ayrıca üçüncü addımdır.


---

# Üçüncü addım: `layout.py`-də sətir bölünməsi (eyni gün)

Yuxarıdakı «3-cü səbəb» həll olundu: bir məhsul sətrinə bir neçə kartın yazısı
yığılırdı.

## Səbəb — şəbəkədən düşən kart

Səhifədə **175 qırmızı qutu** var, amma yalnız **102-sinin qiyməti oxunur**
(Araz-da qiymət ikimərtəbəli yazılır). Qiyməti oxunmayan qutu şəbəkədən
**tamamilə çıxırdı**, onun sözləri isə «özündən sonrakı ilk lövbərə» axıb
qonşu kartın mətninə qarışırdı.

Düzəliş: şəbəkə **bütün** qırmızı qutulardan qurulur. Qiymətsiz qutu kart
yaratmır, amma öz xanasını **sahiblənir** — sözləri qonşuya getmir, atılır.

Lövbərlər **ölçüyə görə** süzülür (`_grid_landmarks`, 0.6–1.6 median): süzgəcsiz
variantda endirim nişanı («32%» qırmızı ləkəsi) də xana tutur və qonşu kartı
boşaldırdı.

## Sınanan, sonra ATILAN variant

İlk variant sözün lövbərdən məsafəsini `_grid_step()` ilə məhdudlaşdırırdı.
**Ölçüldü və səhv çıxdı:** `_grid_step()` kartın eni deyil — o, qonşu qiymət
qutuları arasındakı median məsafədir və qutular yan-yana düşəndə kiçilir
(6-cı səhifədə **112**, halbuki kart ~250 pikseldir). Nəticə: kartın öz sözləri
kəsilirdi — «Nestle Damak Şokolad» → «Şokolad», «Lotte Choco Pie» → «Lotte Pie».
Sərhəd atıldı, şəbəkənin özü düzəldildi.

## Nəticə — kart mətnləri (20 səhifə, 102 kart)

| | Əvvəl | Sonra |
|---|---|---|
| 12 sözdən uzun kart (qarışıq sətir) | 6 | **1** |
| Ən uzun kart | 23 söz | 20 söz |
| Mətni boş kart | 14 | 15 |

Nümunələr:

```
«Penstore Karandaş 12 rəng Penstore Qayçı ASH Su qabi» → «ASH Su qabi»
«Chupa Chups q 25% 18% Mentos Saqqız 15.5 q»           → «Mentos Saqqız 15.5 q»
«Sf Nescafe Qəhvə 145q Starbucks Premium qəhvə»        → «Sf Nescafe Qəhvə 145q»
«...Seyidoğlu Bizim Tarla Şokolad pastası 400 q...»    → «Bizim Tarla ...cemi 300q»
```

Yəni bu sənəddə sadalanan səhvlərin **mənbəyi** qurudu.

## Amma mövcud bazada nəticə İKİ TƏRƏFLİDİR

Şəkil uyğunlaşdırması **saxlanılmış `raw_line`** ilə **canlı kart mətnini**
tutuşdurur. `raw_line` sətirləri KÖHNƏ layout ilə yazılıb — yəni qarışıqdır.
Kart mətni təmizləndikcə oxşarlıq **düşür** və 0.55 həddini keçmir:

| | Düzəlişdən əvvəl | Sonra |
|---|---|---|
| Şəkil | 62 | **51** |
| Doğru | 48 (77%) | **42 (82%)** |
| **Səhv** | 10 (16%) | **6 (12%)** |
| Şübhəli | 4 | 3 |

Səhv nisbəti azaldı (16% → 12%), amma **6 doğru şəkil də itdi** — çünki onların
`raw_line`-ı köhnədir. İtən 11-in 4-ü səhv idi (#1921, #1956, #1966, #1969),
7-si doğru/şübhəli (#1940, #1941, #1942, #1949, #1951, #1964, #1973).

**Bu, düzəlişin qüsuru deyil, köhnə datanın nəticəsidir.** Tam faydanı görmək
üçün kataloq **yenidən emal olunmalıdır** (`raw_line` yenidən yazılsın) — o,
LLM zəncirini işə salır və ayrıca qərardır. Qalan 6 səhv: #1927, #1939, #1950,
#1959, #1968, #2381.


---

# Dördüncü addım: kataloq yenidən emal olundu

Yuxarıda deyilirdi ki, layout düzəlişinin tam faydası görünmür, çünki
`raw_line` köhnə layout ilə yazılıb. Kataloq yenidən emal olundu:
OCR (düzəlmiş layout) → LLM zənciri → baza.

## Yolda tapılan səhv — MƏNİM səhvim

İlk yenidən emalı `OCR_MAX_PAGES=20` ilə işlətdim və məhsul sayı çökdü:
Araz 188 → 69, qiymət sətri 183 → 62. Bunu «layout düzəlişi datanı qırdı»
kimi oxumaq asan olardı.

**Ölçdüm və səbəb başqa çıxdı.** Köhnə və yeni kart mətnlərini eyni
təmizləyicidən keçirdim: **83 → 78 sətir**, yəni layout cəmi 5 sətir aparıb.
Əsl səbəb: köhnə mətn kataloqun **54 səhifəsindən** gəlirdi, mənim emalım isə
yalnız 20 səhifədən. 54 səhifə ilə təkrarladım — mətn yenə **478 sətir** oldu,
tam köhnə fayl kimi.

Dərs: rəqəm düşəndə ilk günahkar ən son dəyişiklik olur, amma o, çox vaxt
günahkar deyil. Ayrı-ayrı ölçmək tələb olunur.

## Yekun nəticə

| | Başlanğıc | Uyğunlaşma | + layout | + yenidən emal |
|---|---|---|---|---|
| Şəkil | 73 | 62 | 51 | **60** |
| **Doğru** | 48 (66%) | 48 (77%) | 42 (82%) | **50 (83%)** |
| **Səhv** | **21 (29%)** | 10 (16%) | 6 (12%) | **6 (10%)** |
| Şübhəli | 4 | 4 | 3 | 4 |
| Unikal kadr | 63/73 | 62/62 | 51/51 | **60/60** |

Araz məhsulları: **183** (əvvəl 188), qiymət sətri **177** (əvvəl 183).
Yəni əhatə bərpa olundu, səhv isə üç dəfə azaldı.

## Səhv şəkillərin mənbəyi qurudu

Yenidən emaldan sonra kartlar **öz məhsullarını tapdı**:

| Kart | Əvvəl kimə düşürdü | İndi kimindir |
|---|---|---|
| ASH Su qabı 5.79 | «karandaş [Penstore]» | **#2571 su qabı [ASH]** |
| Bizim Tarla ərik/şaftalı cemi | «şokolad pastası [Seyidoğlu]» | **#2605 ərik/şaftalı cemi** |
| Nestle Şaqayka 190q | «şokolad [Nestle]» (Aquşa şəkli ilə) | öz sətrinə |
| Yemək qabı və termos dəsti | heç kimə | **#2564 termos** |

## Qalan 6 səhv artıq ŞƏKİL səhvi deyil

#1927 (armudu stəkan → marmelad), #1939 (dondurma → Zabava kreker),
#2381 (qaymaq → plastilin), #2600 (Starbucks → Nesquik), #2609 (duz → sous),
#2614 (qrafin dəsti → Tac cola).

Bunlarda kart **doğru tapılır**, amma LLM həmin sətirdən **yanlış ad** çıxarır:
kart «Süfrə Sous» deyir, bazadakı ad isə «duz». Yəni növbəti addım şəkil
qatında deyil, **atribut çıxarmadadır**.

## Yetim məhsullar təmizləndi

`save_products()` kataloqun qiymətlərini silib yenidən yazır, `products`
cədvəlinə isə toxunmur — ona görə əvvəlki emalın məhsulu qiymətsiz qalır.
Yenidən emaldan sonra 46 belə sətir vardı. `tools/purge_orphans.py` ilə
silindi: **234 → 188 məhsul, yetim 0**.


---

# Beşinci addım: atribut çıxarma

Yuxarıda «qalan 6 səhv artıq şəkil səhvi deyil, LLM yanlış ad çıxarır»
yazılmışdı. Diaqnostika bunu yalnız qismən təsdiqlədi.

**Sınandı və ATILDI:** adın xam sətirdə əsaslandırılması. Gözlə təsdiqlənmiş
60 hökmlə ölçüldü — ən yaxşı variant 6 səhvdən 3-ünü tutub 50 doğrudan 10-nu
atır. Səbəb: model bəzən dünya biliyi ilə doğru ad verir («Heineken» → «pivə»).

**Tapıldı və düzəldildi:** ölçü qiymətə bərabər olan 3 sətir (`unit_price`
tam 1.0 — saxta «ən sərfəli» lideri). `price_reused_as_size()` onları tutur,
məhsulu deyil yalnız ölçünü atır.

## Yekun

| | Başlanğıc | Uyğunlaşma | + layout | + yenidən emal | + atribut |
|---|---|---|---|---|---|
| Şəkil | 73 | 62 | 51 | 60 | **61** |
| Doğru | 48 (66%) | 48 (77%) | 42 (82%) | 50 (83%) | **52 (85%)** |
| **Səhv** | **21 (29%)** | 10 (16%) | 6 (12%) | 6 (10%) | **6 (10%)** |

Qalan 6 səhvin təsnifatı:
- **sətir qarışığı (2):** #1927, #2600 — bir sətirdə iki kartın yazısı qalıb;
- **qiymət toqquşması (1):** #2614 — çıxarma düzdür, kart eyni qiymətlidir;
- **brenddən uydurma ad (3):** #1939 Zabava→dondurma, #2381 ETTA→qaymaq,
  #2609 Süfrə→duz. Bunlar üçün ölçdüyüm yeganə həll faydadan çox zərər verir.
