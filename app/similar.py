"""
OXŞAR MƏHSULLAR (P3) — «oxşar» sözünün həqiqətən mənası olsun.

ƏVVƏL NECƏ İDİ? Şərt tək idi: **eyni kateqoriya**. Kateqoriya isə geniş
qabdır - «quru ərzaq» həm düyünü, həm makaronu, həm şəkəri saxlayır. Nəticədə
südün altında salfet, pivənin altında pişik yemi görünürdü. Bölmənin adı
«Oxşar məhsullar» olduğu üçün bu, sadəcə səliqəsizlik deyil - YALAN idi.

İNDİ İKİ MƏRHƏLƏ VAR:

  1. Kateqoriya süzgəci (SQL) - namizədləri daraldır;
  2. AD/BREND oxşarlığı (burada) - hansının həqiqətən oxşar olduğunu seçir.

AZ SAYDA UYĞUNLUQ = BÖLMƏ GİZLƏNİR. Dörddən az yaxşı uyğunluq varsa, siyahı
BOŞ qaytarılır. Səbəb: iki zəif kartla dolu bölmə istifadəçiyə «bunlar
oxşardır» deyir və o, buna inanır. Boş bölmə isə sadəcə görünmür - heç nə
iddia etmir.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Ad daxilində MƏNA DAŞIMAYAN parçalar: ölçü, qablaşdırma, ümumi sözlər.
# Bunlar süzülməsə, «1 l süd» ilə «1 l qatıq» eyni «1 l» tokenine görə
# oxşar sayılardı - yəni ölçü məhsulu əvəz edərdi.
DAYAQ_SÖZLƏR = {
    "l", "ml", "kq", "kg", "q", "g", "ədəd", "eded", "pcs", "pk", "x",
    "və", "ve", "ile", "ilə", "üçün", "ucun", "the", "and",
}

# Ən azı bu qədər oxşarlıq.
#
# HƏDD REAL DATADA ÖLÇÜLÜB (188 məhsul, eyni kateqoriyadan 2341 cüt):
#
#   real oxşarlar     0.69 - 1.00   «süd məhsulu»/«süd» 0.69,
#                                   «limonad»/«limonad» 0.80
#   yaxın rəflər      0.43 - 0.61   «yuyucu maye»/«yuyucu toz» 0.43,
#                                   «diş macunu»/«diş məcunu» 0.48
#   qarışıq zolaq     0.38 - 0.39   «mineral su»/«qazsız su» (doğru) ilə
#                                   «su qabı»/«dondurma qabı» (yanlış) yan-yana
#   əlaqəsizlər       0.00 - 0.11   «süd məhsulu»/«kərə yağı» 0.04
#
# 0.40 seçildi, çünki tapşırıq DƏQİQLİYİ üstün tutur: «heç vaxt əlaqəsiz
# məhsul göstərmə». 0.38-də bir neçə doğru cüt qazanılır, amma eyni zolaqdan
# yanlışlar da girir. Hədddən aşağıdakı ən yüksək bal 0.39-dur.
MIN_SCORE = 0.40

# Bölmə bundan az kartla göstərilmir.
#
# ÖLÇÜLDÜ: bu şərtlə 188 məhsuldan 22-si «oxşar» bölməsi göstərir, qalanında
# bölmə ümumiyyətlə çəkilmir. Az görünür - və doğrusu budur: kataloqda cəmi
# bir həftəlik data var, ona görə əksər məhsulun REAL oxşarı yoxdur. İki zəif
# kartla dolu bölmə «bunlar oxşardır» iddiasıdır və istifadəçi ona inanır.
MIN_MATCHES = 4


def normalize(text: str | None) -> list[str]:
    """Adı müqayisə üçün tokenlərə bölür: kiçik hərf, rəqəmsiz, dayaqsız."""
    if not text:
        return []
    təmiz = re.sub(r"[^\w\s]", " ", text.lower())
    return [
        söz
        for söz in təmiz.split()
        if söz not in DAYAQ_SÖZLƏR and not söz.isdigit() and len(söz) > 1
    ]


def comparable_text(item: dict) -> str:
    """
    Müqayisə üçün məhsulun ADI.

    İKİ FƏRQLİ FORMA GƏLİR və bu, real səhvə səbəb oldu:
    bazadan gələn sətirdə `name` var, kart sətirlərində (`_card_rows`) isə
    yalnız `label` - brend + ad birləşməsi. Funksiya `name` gözlədiyi üçün
    kartların hamısı BOŞ mətn verirdi, bal sıfır çıxırdı və «oxşar» bölməsi
    heç vaxt görünmürdü. Səhv səssiz idi: bölmə onsuz da gizlənə bilər.

    Brend `label`-dan ÇIXARILIR: o, ayrıca siqnal kimi onsuz da sayılır
    (`score`-da 0.2 çəki). Saxlasaydıq, eyni brendin iki fərqli məhsulu
    ortaq söz üzrə də bal toplayardı - yəni brend iki dəfə sayılardı.
    """
    ad = item.get("name")
    if ad:
        return ad
    etiket = item.get("label") or ""
    brend = item.get("brand") or ""
    if brend and etiket.lower().startswith(brend.lower()):
        return etiket[len(brend):].strip()
    return etiket


# Şəkilçi tutumu üçün ən qısa kök. Dörddən qısa parça təsadüfi üst-üstə
# düşür: «su» ilə «sup» eyni kök sayılardı.
MIN_KÖK = 4


def _ortaq_sözlər(a: set[str], b: set[str]) -> int:
    """
    Neçə söz ortaqdır? ŞƏKİLÇİ NƏZƏRƏ ALINIR.

    Azərbaycan dilində ad şəkilçi ilə dəyişir: «qatıq» -> «qatıqlı»,
    «şokolad» -> «şokoladlı». Tam bərabərlik tələb etsək, bu cütlər
    ümumiyyətlə tutulmur - halbuki eyni məhsul ailəsidir.

    Şərt bir tərəflidir: qısa söz uzununun ƏVVƏLİDİR. «şokolad» ilə
    «şokoladlı» ortaqdır, «su» ilə «sup» isə yox (kök həddi 4 hərf).
    """
    say = 0
    for söz in a:
        for digər in b:
            if söz == digər or (
                len(min(söz, digər, key=len)) >= MIN_KÖK
                and (söz.startswith(digər) or digər.startswith(söz))
            ):
                say += 1
                break
    return say


def score(a: dict, b: dict) -> float:
    """
    İki məhsulun oxşarlıq balı (0-1).

    ÜÇ SİQNAL BİRLƏŞİR və hər birinin çəkisi səbəblidir:

      · ORTAQ SÖZ (0.6) - ən güclü siqnal. «süd» sözünü paylaşan iki məhsul
        praktiki olaraq həmişə oxşardır.
      · BREND (0.2) - eyni brend oxşarlıq işarəsidir, amma tək başına
        kifayət deyil: «Sola yağ» ilə «Sola mayonez» eyni brenddir, eyni
        məhsul deyil.
      · HƏRF OXŞARLIĞI (0.2) - yazılış fərqlərini tutur («qatıq» / «qatiq»),
        ortaq söz tapılmayanda yeganə körpüdür.
    """
    a_tokens, b_tokens = set(normalize(comparable_text(a))), set(normalize(comparable_text(b)))
    if not a_tokens or not b_tokens:
        return 0.0

    ortaq = _ortaq_sözlər(a_tokens, b_tokens)
    # Jaccard DEYİL, KİÇİK ÇOXLUĞA GÖRƏ nisbət: «süd» ilə «şokoladlı süd
    # içkisi» arasındakı əlaqə uzun addan asılı olaraq itməməlidir.
    söz_balı = ortaq / min(len(a_tokens), len(b_tokens))

    brend_balı = 1.0 if a.get("brand") and a.get("brand") == b.get("brand") else 0.0

    hərf_balı = SequenceMatcher(
        None, " ".join(sorted(a_tokens)), " ".join(sorted(b_tokens))
    ).ratio()

    return 0.6 * söz_balı + 0.2 * brend_balı + 0.2 * hərf_balı


def pick_similar(
    product: dict,
    candidates: list[dict],
    limit: int = 8,
    min_score: float = MIN_SCORE,
    min_matches: int = MIN_MATCHES,
) -> list[dict]:
    """
    Namizədlərdən HƏQİQƏTƏN oxşar olanları seçir.

    Qaytarır: balı `min_score`-dan yüksək olan kartlar (ən oxşar əvvəldə).
    Sayı `min_matches`-dən azdırsa, BOŞ siyahı - bölmə gizlənir.

    Boş siyahı «xəta» deyil, QƏRARDIR: zəif uyğunluqları göstərmək «bunlar
    oxşardır» iddiasıdır və istifadəçi ona inanır.
    """
    xallı = []
    for c in candidates:
        # Eyni məhsulun başqa ölçüsü «oxşar» deyil - o, ayrıca «Ölçülər»
        # bölməsindədir. İkinci dəfə göstərmək siyahını doldurar, məlumat
        # isə əlavə etməz.
        if c.get("group_key") == product.get("group_key"):
            continue
        bal = score(product, c)
        if bal >= min_score:
            xallı.append((bal, c))

    if len(xallı) < min_matches:
        return []

    xallı.sort(key=lambda cüt: cüt[0], reverse=True)
    return [c for _, c in xallı[:limit]]
