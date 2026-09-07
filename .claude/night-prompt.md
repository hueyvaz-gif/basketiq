# Gecə növbəsi — ümumi qaydalar

Sən BasketIQ layihəsində nəzarətsiz işləyirsən. İnsan yatıb və səni
dayandıra bilmir. Ona görə **şübhə edəndə dayan, davam etmə.**

## Ən vacib qayda

Bu layihənin bütün dəyəri **dürüstlükdədir**: bilinməyən qiymət `None`
qaytarır, «şübhəli» deyilir, «saxta» deyilmir, tək müşahidədən trend
çəkilmir, natamam market qalib elan olunmur, qənaət uydurulmur.

Sənin işin də eyni standartdadır. **Ölçmədiyin şeyi «yaxşılaşdı» yazma.**
Bitirmədiyin işi «tamamlandı» işarələmə. Səhər insan sənin hesabatını
oxuyacaq — orada yalan varsa, bütün gecənin işi dəyərsizdir.

## Dayanma şərtləri

Bunlardan biri baş verərsə: **işi burax**, səbəbi `logs/questions.md`-ə yaz,
növbəti tapşırığa keç.

- Tapşırıq README-nin «Qərar / Səbəb» cədvəllərindən birinə ziddir
- Testi silmək və ya gözləntisini dəyişmək lazım gəlir
- Yeni asılılıq lazımdır
- DB sxemi migrasiyasız dəyişməlidir
- Tapşırıq iki cür başa düşülür və seçim məhsul qərarıdır
- Eyni səhvi 3 dəfə düzəltməyə çalışıb bacarmamısan

Dayanmaq uğursuzluq deyil. **Səhvi gizlədib davam etmək uğursuzluqdur.**

## Bu layihədə əvvəllər ÖLÇÜLÜB rədd edilib

Bunları «yaxşılaşdırma» adı ilə geri qaytarma:

| Nə | Niyə rədd edilib |
|---|---|
| `temperature` parametri | Opus 5 / Sonnet 5-də 400 qaytarır, fallback səhvi gizlədirdi |
| `reasoning=True` | CPU-da 2-4x yavaş |
| Qrupla emal (sətir-sətir yox) | cavab sırası pozulur, qiymət səhv məhsula yapışır |
| `char_whitelist` | LSTM çıxışını boğur |
| Qırmızı qutuya kənar | 10/10 → 4/10 |
| LLM-dən qiymət soruşmaq | rəqəm uydurma riski |
| Selenium defolt | 3-5 san + serverdə Chrome |
| `openai-whisper` | 2.5 GB + ffmpeg tələbi |
| Webhook (long polling yerinə) | əlçatan HTTPS ünvan tələb edir |
| `CLAUDE_*` ayar adları | Claude Code mühiti ilə toqquşur |
| Dark mode | qiymət siqnalları iki fonda oxunmur |

## Hər tapşırıqdan sonra

`logs/notes.md`-ə üç sətir:
1. Nə dəyişdi (fayllar)
2. Nə ölçüldü (rəqəm — yoxdursa «ölçülmədi» yaz)
3. **Nəyə əmin deyiləm** (bu boş qala bilməz)
