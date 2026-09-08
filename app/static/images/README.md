# Market loqoları

Ana səhifədəki market şəbəkəsi (`store-grid.js`) və market səhifəsi
(`store.js`) loqoları buradan oxuyur.

## Gözlənilən fayllar

| Fayl | Market | Reyestrdəki slug |
|---|---|---|
| `araz.png` | Araz Market | `araz` |
| `bravo.png` | Bravo Market | `bravo` |
| `bazar.png` | Bazar Store | `bazar-store` |
| `rahat.png` | Rahat Market | `rahat` |

Fayl adları `app/stores.py`-dəki `Market.logo` sahəsindən gəlir — yeganə
mənbə odur. Ad dəyişəcəksə, orada dəyişdirin; frontend-də ayrıca siyahı
saxlanılmır.

## Fayl yoxdursa nə olur?

**Səhifə sınmır.** Şəkil yüklənməyəndə `error` hadisəsi baş verir, JS şəkli
silib yerinə marketin adını yazır (`.store-wordmark`). Yəni loqolar qovluğa
qoyulana qədər şəbəkə mətn nişanları ilə işləyir.

Uydurma loqo ÇƏKİLMİR: saxta brend nişanı istifadəçini yanıldar, üstəlik
başqasının markasını təqlid etməkdir.

## Tövsiyə olunan format

- PNG, şəffaf fon
- ~240×120 px (qutu 72px hündürlükdədir, `object-fit: contain` sığdırır)
- Loqonun ətrafında artıq boşluq olmasın — qutu onsuz da boşluq verir
