"""
Düşünmə (chain-of-thought) filtri.

NİYƏ BU TESTLƏR VACİBDİR?
Filtr istifadəçi ilə modelin XAM cavabı arasındakı yeganə maneədir. Sınsa,
səhv görünmür - sadəcə tövsiyənin əvvəlinə modelin öz-özü ilə söhbəti düşür
və istifadəçi onu "cavab" kimi oxuyur.

İki risk ayrıca sınanır:
  1. AXIN: `<think>` etiketi iki token arasında bölünə bilər. Ona görə hər
     hal 1, 3, 7 və "hamısı bir yerdə" ölçüləri ilə yoxlanılır.
  2. YALANÇI POZİTİV: normal cümlədəki "reasoning" sözü və ya "<" işarəsi
     silinməməlidir.
"""

import pytest

from ai.sanitize import ReasoningFilter, strip_reasoning


def run_stream(text: str, size: int) -> str:
    """Mətni `size` uzunluqlu parçalarla filtrdən keçirir - SSE-nin taxlidi."""
    flt = ReasoningFilter()
    out = [flt.feed(text[i:i + size]) for i in range(0, len(text), size)]
    out.append(flt.flush())
    return "".join(out)


# Parça ölçüsü nəticəyə TƏSİR ETMƏMƏLİDİR - filtrin əsas zəmanəti budur.
CHUNK_SIZES = [1, 3, 7, 1000]


@pytest.mark.parametrize("size", CHUNK_SIZES)
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("<think>Okay, let me work through this...</think>Araz seçin.", "Araz seçin."),
        ("Araz <think>hmm</think>ucuzdur.", "Araz ucuzdur."),
        ("<THINK>böyük hərflə</THINK>Araz.", "Araz."),
        ("<thinking>uzun</thinking>Araz.", "Araz."),
        ("[thinking]mötərizəli[/thinking]Araz.", "Araz."),
        ("<think>a</think>Bir.<think>b</think>İki.", "Bir.İki."),
        # Bağlanmayan etiket: qalan hər şey düşüncədir
        ("<think>model kəsildi", ""),
        # Etiket yoxdursa mətn TOXUNULMAZ qalır
        ("Araz marketini seçin, 2.45 AZN qənaət edirsiniz.", "Araz marketini seçin, 2.45 AZN qənaət edirsiniz."),
    ],
)
def test_axin_filtri(raw, expected, size):
    assert run_stream(raw, size) == expected


@pytest.mark.parametrize("size", CHUNK_SIZES)
def test_normal_mətndəki_kiçikdir_işarəsi_silinmir(size):
    """`<` hər zaman etiket demək deyil - riyazi işarə də ola bilər."""
    text = "Qiymət < 20 AZN olmalıdır."
    assert run_stream(text, size) == text


def test_reasoning_sözü_cümlədə_qalır():
    """
    Yalnız BLOK STRUKTURU silinir.

    Bu, tapşırığın açıq tələbidir: "reasoning" sözü normal cümlədə keçirsə
    toxunulmamalıdır. Marker sətrin əvvəlində və ikinöqtə ilə olmalıdır.
    """
    text = "Bunun reasoning hissəsi maraqlıdır, amma Araz ucuzdur."
    assert strip_reasoning(text) == text


def test_sətir_başındakı_etiket_silinir():
    raw = "Reasoning: model belə düşünür\nikinci sətir\n\nAraz ucuzdur."
    assert strip_reasoning(raw) == "Araz ucuzdur."


def test_son_cavab_markerindən_əvvəlki_atılır():
    raw = "Uzun-uzadı düşüncə mətni burada.\nCavab: Araz marketini seçin."
    assert strip_reasoning(raw) == "Araz marketini seçin."


def test_boş_son_cavab_mətni_silmir():
    """
    Model "Cavab:" yazıb kəsilibsə, mətni ATMIRIQ.

    Əks halda istifadəçi tamamilə boş kart görərdi - yarımçıq mətn heç
    nədən yaxşıdır.
    """
    raw = "Araz ucuzdur.\nCavab:"
    assert strip_reasoning(raw) == raw


def test_boş_giriş():
    assert strip_reasoning("") == ""
    assert strip_reasoning(None or "") == ""


def test_artıq_boşluqlar_yığışdırılır():
    raw = "<think>x</think>\n\n\n\nAraz ucuzdur.   \n"
    assert strip_reasoning(raw) == "Araz ucuzdur."
