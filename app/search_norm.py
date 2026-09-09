"""
AXTARIŞ NORMALLAŞDIRMASI — diakritiksiz yazılan sorğu da tapsın (M0).

PROBLEM REALDIR VƏ GÜNDƏLİKDİR: telefon klaviaturasında «düşbərə» yazmaq
üçün altı dəfə uzun basmaq lazımdır, adam isə «dusbere» yazır. Köhnə axtarış
`LIKE '%dusbere%'` ilə HEÇ NƏ tapmırdı - məhsul bazada var, istifadəçi isə
«yoxdur» cavabı alırdı.

İKİ QAYDA BÜTÜN FAYLA HAKİMDİR:

1. ƏVƏZLƏMƏ 1:1-DİR. «ə» → «e», genişlənmə yoxdur («ae» kimi). Səbəb:
   normallaşmış mətndəki mövqe orijinal mətndəki mövqe ilə ÜST-ÜSTƏ
   düşməlidir - əks halda uyğunluğu ekranda işıqlandırmaq üçün indeksləri
   yenidən hesablamaq lazım gələr və hər səhv bir hərf sürüşməsi ilə çıxar.

2. ƏVVƏL FOLD, SONRA KİÇİK HƏRF. Azərbaycan əlifbasında «I» → «ı» və
   «İ» → «i»-dir; Python-un `lower()`-i isə lokaldan asılı deyil və «I» → «i»
   verir. Ardıcıllığı tərsinə çevirsək, «İSTİ» sözü platformadan asılı olaraq
   iki cür normallaşardı. Fold hər iki böyük hərfi ASCII «i»-yə salır, ondan
   sonra `lower()` heç nəyi dəyişmir.

CƏDVƏL BURADA - YEGANƏ MƏNBƏDİR. `app/static/search-norm.js` eyni cədvəli
saxlayır, çünki brauzer də eyni fold-u tətbiq edir. İki nüsxənin ayrılmasının
qarşısını `tests/test_search_norm.py` alır: JS faylı oxunur və cədvəl
hərfbəhərf tutuşdurulur. Fərq yaransa test düşür.
"""

from __future__ import annotations

# Azərbaycan hərfi -> ASCII qarşılığı. Hər tərəf BİR simvoldur.
FOLD_MAP: dict[str, str] = {
    "ə": "e", "Ə": "e",
    "ı": "i", "I": "i",
    "İ": "i",
    "ö": "o", "Ö": "o",
    "ü": "u", "Ü": "u",
    "ş": "s", "Ş": "s",
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
}

_TABLE = str.maketrans(FOLD_MAP)


def fold(text: str | None) -> str:
    """
    Mətni müqayisə formasına salır: diakritiksiz, kiçik hərflərlə.

    UZUNLUQ DƏYİŞMİR - bu, təsadüf deyil, tələbdir:

        len(fold(s)) == len(s)

    Ekranda ad HƏMİŞƏ orijinal formada görünür; fold yalnız müqayisə üçündür.
    """
    if not text:
        return ""
    return text.translate(_TABLE).lower()


def tokens(text: str | None) -> list[str]:
    """
    Sorğunu/adı sözlərə bölür (normallaşdırılmış).

    Çoxsözlü sorğu VƏ məntiqi ilə işləyir: «araz sud» hər iki tokeni ayrıca
    tələb edir. Ona görə bölgü axtarış tərəfində də, məhsul tərəfində də eyni
    funksiyadan keçməlidir - əks halda «Milla süd 1 l» sətri «1» tokenini bir
    yerdə saxlayıb digərində atardı.
    """
    return [söz for söz in fold(text).replace("-", " ").split() if söz]


# ============================================================================
# UYĞUNLUQ VƏ SIRALAMA (M1)
# ============================================================================
#
# PİLLƏ NÖMRƏSİ ELƏ BALDIR: kiçik rəqəm = daha yaxşı uyğunluq.
#
#   1  tam bərabərlik      «süd» sorğusu «süd» məhsulunu
#   2  söz başlanğıcı      «sud» → «südlü şirniyyat»
#   3  söz ortası          «bere» → «düşbərə»
#   4  bir hərf səhvi      «dusberre» → «düşbərə»
#
# DÖRDÜNCÜ PİLLƏ YALNIZ ƏVVƏLKİ ÜÇÜ BOŞ QAYIDANDA İŞƏ DÜŞÜR. Səbəb ölçülə
# biləndir: «süd» üç hərflidir və ondan bir hərf uzaqlıqda «sud», «sut»,
# «suz», «sud» kimi onlarla söz var - fuzzy həmişə açıq olsa, dəqiq sorğu
# yalançı nəticələrin içində itərdi.

EXACT, PREFIX, SUBSTRING, FUZZY = 1, 2, 3, 4

# Fuzzy YALNIZ uzun tokenlər üçün. Qısa sözdə bir hərf fərqi məna fərqidir:
# «süd» ↔ «sut», «un» ↔ «ün». Beş hərfdən başlayaraq bir hərf səhvi
# praktiki olaraq yazı səhvidir.
MIN_FUZZY_LEN = 5


def _within_one_edit(a: str, b: str) -> bool:
    """
    İki söz arasında ən çox BİR redaktə (əlavə/silmə/dəyişmə) varmı?

    Tam Levenshtein matrisi qurulmur: hədd 1 olduğu üçün uzunluq fərqi 1-dən
    böyük olan cütlər dərhal atılır, qalanı isə tək keçidlə yoxlanılır.
    Bu, sorğunun bütün namizədlərlə müqayisəsində fərqi hiss olunacaq qədər
    ucuzlaşdırır.
    """
    if abs(len(a) - len(b)) > 1:
        return False
    if a == b:
        return True

    # Uzun olanı əvvələ qoyuruq ki, tək qol yazılsın.
    if len(a) < len(b):
        a, b = b, a

    i = j = 0
    fərq = False
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            if fərq:
                return False
            fərq = True
            if len(a) == len(b):
                j += 1      # dəyişmə
            # əks halda: əlavə hərf - yalnız `a` irəliləyir
        else:
            j += 1
        i += 1
    return True


def token_score(token: str, hədəf: str, allow_fuzzy: bool = False) -> int | None:
    """
    Bir sorğu tokeni hədəf mətndə hansı pillədə uyğun gəlir? Yoxdursa `None`.

    `hədəf` NORMALLAŞDIRILMIŞ olmalıdır (`name_norm`). Burada yenidən fold
    etmirik: sütun məhz bunun üçün var.
    """
    if not token or not hədəf:
        return None

    sözlər = hədəf.split()

    if token == hədəf or token in sözlər:
        return EXACT
    if any(söz.startswith(token) for söz in sözlər):
        return PREFIX
    if token in hədəf:
        return SUBSTRING
    if allow_fuzzy and len(token) >= MIN_FUZZY_LEN:
        if any(_within_one_edit(token, söz) for söz in sözlər):
            return FUZZY
    return None


def match_score(hədəf: str, sorğu_tokenləri: list[str], allow_fuzzy: bool = False) -> int | None:
    """
    Bütün sorğu tokenləri hədəfdə tapılırmı? Tapılırsa - ƏN PİS pillə.

    VƏ MƏNTİQİ: «araz sud» sorğusunda hər iki söz uyğun gəlməlidir. Biri
    tapılmasa nəticə `None`-dur - «ya biri, ya digəri» məntiqi axtarışı
    faydasız edərdi, çünki ikinci söz elə birinciyə əlavə edilən süzgəcdir.

    ƏN PİS PİLLƏ SEÇİLİR (max), ən yaxşısı yox: «milla» dəqiq, «sud» isə
    yazı səhvi ilə uyğun gəlirsə, nəticənin etibarı zəif olan tərəfə görə
    qiymətləndirilməlidir.
    """
    if not sorğu_tokenləri:
        return None

    ən_pis = 0
    for token in sorğu_tokenləri:
        bal = token_score(token, hədəf, allow_fuzzy)
        if bal is None:
            return None
        ən_pis = max(ən_pis, bal)
    return ən_pis
