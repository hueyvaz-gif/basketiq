# Market loqoları

Ana səhifədəki market şəbəkəsi (`store-grid.js`) və market səhifəsi
(`store.js`) loqoları buradan oxuyur.

## Fayllar

| Fayl | Market | Slug | Ölçü | Nisbət | Fon |
|---|---|---|---|---|---|
| `araz.png` | Araz Market | `araz` | 820×252 | 3.25 | şəffaf |
| `bravo.png` | Bravo Market | `bravo` | 1263×309 | 4.09 | şəffaf |
| `bazar.png` | Bazar Store | `bazar-store` | 647×114 | 5.68 | şəffaf |
| `rahat.png` | Rahat Market | `rahat` | 252×149 | 1.69 | **ağ (şəffaf deyil)** |

Fayl adları `app/stores.py`-dəki `Market.logo` sahəsindən gəlir — yeganə
mənbə odur. Ad dəyişəcəksə, orada dəyişdirin; frontend-də ayrıca siyahı
saxlanılmır.

## Fayl yoxdursa nə olur?

**Səhifə sınmır.** Şəkil yüklənməyəndə `error` hadisəsi baş verir, JS şəkli
silib yerinə marketin adını yazır (`.store-wordmark`). Yəni loqolar qovluğa
qoyulana qədər şəbəkə mətn nişanları ilə işləyir.

Uydurma loqo ÇƏKİLMİR: saxta brend nişanı istifadəçini yanıldar, üstəlik
başqasının markasını təqlid etməkdir.

## İki bilinən detal

**1. `rahat.png`-in fonu ağdır, şəffaf deyil.** Ona görə «Tezliklə»
kartlarının fonu boz (`--surface`) yox, AĞ saxlanılıb — boz fonda həmin loqo
ağ düzbucaq kimi görünürdü. «Tezliklə» siqnalı kəsik çərçivə və yazı ilə
verilir, fonla yox (`style.css`, `.store-card.is-soon`).

**2. `rahat.png` digərlərindən kiçik görünür.** Səbəb faylın ÖZ daxili
boşluğudur: 252×149 şəkildə söz nişanının ətrafında xeyli ağ sahə var, qutu
isə şəkli bütövlükdə sığdırır. Daha yığcam kəsilmiş nüsxə qoyulsa, avtomatik
olaraq böyük görünəcək — kodda dəyişiklik lazım deyil.

## Tövsiyə olunan format

- PNG, **şəffaf** fon
- nisbət 3:1 ətrafında (qutu 72px hündürlükdədir, `object-fit: contain` sığdırır)
- Loqonun ətrafında artıq boşluq olmasın — qutu onsuz da boşluq verir
