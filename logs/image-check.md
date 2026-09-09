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

## Nə edilmədi

Kod **dəyişdirilmədi** — bu sənəd yalnız ölçmədir. Düzəliş ayrı qərardır və
ən azı üç addım tələb edir: bir-birə uyğunlaşma, qiymət açarının məcburi
edilməsi, kadrın öz fotosunun tapılması.
