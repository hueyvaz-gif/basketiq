"""
KATALOQ DİZAYNI PROFİLLƏRİ (`ingestion/layout.py:LayoutStyle`).

NİYƏ BU FAYL VAR: analizator əvvəl YALNIZ Arazın dizaynını bilirdi - lövbər
kimi qırmızı qutu axtarırdı. Rahat kataloqunda qiymət sarı etiketdədir və
nəticə səssiz idi: `parse_page` 0 lövbər tapır, adi OCR-a düşür, 486
sətirdən 6-sı qalır. Testlər iki dizaynın bir-birinə qarışmamasını qoruyur.

ŞƏKİL LAZIM DEYİL: burada dizayn TƏSVİRİ yoxlanılır, OCR nəticəsi yox.
"""

import pytest
from PIL import Image

from ingestion.layout import (
    ARAZ_STYLE,
    DEFAULT_STYLE,
    GRAY_RANGE,
    RAHAT_STYLE,
    RED_RANGE,
    STYLES,
    YELLOW_RANGE,
    style_for,
)
from ingestion.ocr import _spread_halves
from ingestion.profiles import PROFILES


def test_defolt_araz_dizaynidir():
    """
    Dizayn verilməyəndə davranış DƏYİŞMƏMƏLİDİR: Arazın 379 məhsulu mövcud
    yolla oxunur və yeni məntiq ona toxunmamalıdır.
    """
    assert DEFAULT_STYLE is ARAZ_STYLE
    assert style_for(None) is ARAZ_STYLE
    assert style_for("araz") is ARAZ_STYLE


def test_taninmayan_ad_defolta_dusur():
    """Ad səhvi kataloq emalını DAYANDIRMAMALIDIR."""
    assert style_for("yoxdur") is ARAZ_STYLE
    assert style_for("") is ARAZ_STYLE


def test_iki_dizayn_lovber_rengi_ile_ferqlenir():
    """
    ƏSAS FƏRQ: Arazda yeni qiymət QIRMIZI qutudadır, Rahat-da SARI.
    Bu sətir pozulsa, Rahat yenidən 0 lövbər tapar.
    """
    assert ARAZ_STYLE.anchor == RED_RANGE
    assert RAHAT_STYLE.anchor == YELLOW_RANGE
    assert RAHAT_STYLE.secondary == GRAY_RANGE


def test_metn_tonu_dizayna_gore_terslenir():
    """
    Araz: qırmızı qutu + AĞ rəqəm. Rahat: sarı qutu + QARA rəqəm.
    Səhv istiqamət qiyməti oxunmaz edir (eşik tərsinə işləyir).
    """
    assert ARAZ_STYLE.anchor_dark_text is False
    assert RAHAT_STYLE.anchor_dark_text is True


def test_kohne_qiymetin_yeri_dizayna_gore_deyisir():
    """Arazda köhnə qiymət lövbərin ÜSTÜNDƏ, Rahat-da ALTINDADIR."""
    assert ARAZ_STYLE.secondary_above is True
    assert RAHAT_STYLE.secondary_above is False


def test_araz_ucun_sesverme_SONULUDUR():
    """
    Səsvermə YALNIZ ona ehtiyacı olan dizayna qoşulur. Araz üçün açılsa,
    onun 379 məhsulunun oxunuşu dəyişə bilərdi - qazancsız risk.
    """
    assert ARAZ_STYLE.price_vote_min == 0
    assert ARAZ_STYLE.price_split_geoms == ()
    assert RAHAT_STYLE.price_vote_min >= 3


def test_rahat_ucun_qebul_heddi_sertdir():
    """
    Ölçüldü (14 etiket): hədd yoxdur -> 9 düz, 2 SƏHV; 3 səs/0.75 -> 5 düz,
    0 səhv. Səhv qiymət müqayisə saytında istifadəçini yanlış markete
    göndərir, ona görə sərt hədd seçilib.
    """
    assert RAHAT_STYLE.price_vote_share >= 0.75


def test_rahat_kohne_qiymeti_oxumur():
    """
    Ölçüldü: boz qutudan gözlənilən 3.60 əvəzinə 5.23 və 5.83 alındı, süzgəc
    də tutmadı. Səhv köhnə qiymət UYDURMA endirim faizi yaradır - `None`
    isə sadəcə faizin göstərilməməsidir.
    """
    assert RAHAT_STYLE.read_secondary is False
    assert ARAZ_STYLE.read_secondary is True


# ---------------------------------------------------------------- yayım bölməsi


def test_eni_boyuk_sehife_ikiye_bolunur():
    """Rahat PDF-i 3572x2526-dır: yan-yana iki A4."""
    parts = list(_spread_halves(Image.new("RGB", (3572, 2526))))
    assert len(parts) == 2
    assert [p.size for p in parts] == [(1786, 2526), (1786, 2526)]


def test_adi_sehife_bolunmur():
    """Portret səhifə (Araz) toxunulmadan keçir."""
    parts = list(_spread_halves(Image.new("RGB", (1786, 2526))))
    assert len(parts) == 1
    assert parts[0].size == (1786, 2526)


def test_kvadrat_sehife_bolunmur():
    """Sərhəd hal: en == hündürlük yayım sayılmır."""
    assert len(list(_spread_halves(Image.new("RGB", (2000, 2000))))) == 1


# ---------------------------------------------------------------- profil bağı


@pytest.mark.parametrize("slug", sorted(PROFILES))
def test_her_profilin_dizayn_adi_taninir(slug):
    """
    Profil `layout` adını saxlayır, rənglər isə `layout.py`-dədir. Ad
    siyahıda olmasa, market səssizcə Araz dizaynı ilə oxunardı.
    """
    assert PROFILES[slug].layout in STYLES, f"{slug}: tanınmayan dizayn"


def test_rahat_oz_dizaynini_islenir():
    assert PROFILES["rahat"].layout == "rahat"
    assert PROFILES["araz"].layout == "araz"
