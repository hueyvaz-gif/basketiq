"""
Şəkil-məhsul uyğunlaşdırması (`ingestion.images.assign_cards`).

BU MƏNTİQİN TESTİ YOX İDİ - səhv məhz ona görə keçdi. 73 şəkil gözlə
yoxlananda 21-i səhv məhsulu göstərirdi (`logs/image-check.md`); hər iki
səbəb burada bir-bir yoxlanılır.
"""

import pytest

from ingestion.images import AMBIGUITY_GAP, assign_cards, better_reason
from ingestion.layout import Card


def card(text: str, price: float, index: int = 0) -> Card:
    """Səhifədəki bir kart. Qutu koordinatı burada əhəmiyyət daşımır."""
    return Card(text=text, price=price, box=(index * 100, 0, index * 100 + 50, 50))


def target(product_id: int, raw_line: str, price: float) -> dict:
    return {"product_id": product_id, "raw_line": raw_line, "price": price}


def test_bir_kart_iki_məhsula_verilmir():
    """
    REAL SƏHVDƏN ÇIXIB: seçilmiş kart siyahıdan çıxarılmırdı, ona görə
    iki məhsul eyni kartı «qazanırdı». Ölçüldü: 73 fayldan yalnız 63-ü
    unikal idi - «it yemi» ilə «qaymaq» eyni plastilin şəklini göstərirdi.
    """
    cards = [card("ETTA Plastilin 5 rəng", 1.79)]
    targets = [
        target(1, "ETTA Plastilin 5 rəng 1.79", 1.79),
        target(2, "ETTA Plastilin 5 renq 1.79", 1.79),  # OCR fərqi ilə eyni sətir
    ]

    winners, why = assign_cards(targets, cards)

    assert len(winners) == 1, "bir kart yalnız bir məhsula verilməlidir"
    loser = ({1, 2} - {winners[0].product_id}).pop()
    assert why[loser] == "kart tutulub"


def test_qiyməti_uyğun_kart_yoxdursa_şəkil_verilmir():
    """
    REAL SƏHVDƏN ÇIXIB: `pool = priced or cards` sətri qiymət süzgəcini
    məhz ehtiyac olan anda söndürürdü və qərarı yalnız mətn verirdi.
    «Sosis» sətri belə Pringles kartına düşdü.
    """
    cards = [card("Pringles Çips 40 q", 2.49)]
    targets = [target(1, "Sosis 300 q 5.90", 5.90)]

    winners, why = assign_cards(targets, cards)

    assert winners == []
    assert why[1] == "qiymət yoxdur"


def test_kartı_xalı_yüksək_olan_alır_sıra_önəmli_deyil():
    """
    Əvvəl kartı «birinci gələn» alırdı, yəni nəticə `product_id` sırasından
    asılı idi. Eyni giriş fərqli sıra ilə eyni nəticə verməlidir.
    """
    cards = [card("Tuc Kreker 100 q", 1.69)]
    dogru = target(1, "Tuc Kreker 100 q 1.69", 1.69)
    yad = target(2, "Ariel paltar yuyucu vasitə 1.69", 1.69)

    duz, _ = assign_cards([dogru, yad], cards)
    ters, _ = assign_cards([yad, dogru], cards)

    assert duz[0].product_id == 1
    assert ters[0].product_id == 1, "nəticə sıradan asılı olmamalıdır"


def test_zəif_uyğunluq_atılır():
    cards = [card("Borjomi Mineral su 750 ml", 1.89)]
    targets = [target(1, "Heineken pivə banka 500 ml", 1.89)]

    winners, why = assign_cards(targets, cards)

    assert winners == []
    assert why[1] == "zəif"


def test_iki_namizəd_yaxındırsa_şəkil_verilmir():
    """Hansının doğru olduğunu bilmiriksə, placeholder səhv şəkildən yaxşıdır."""
    cards = [card("Araz Süd 1 L", 2.20, 0), card("Araz Süd 1 l", 2.20, 1)]
    targets = [target(1, "Araz Süd 1 L 2.20", 2.20)]

    winners, why = assign_cards(targets, cards)

    assert winners == []
    assert why[1] == "qeyri-müəyyən"


def test_uyğunlaşan_məhsul_səbəb_siyahısında_qalmır():
    """Kart alan məhsul «atıldı» kimi sayılmamalıdır."""
    cards = [card("Nesquik Kakao tozu 420 q", 9.79)]
    targets = [target(1, "Nesquik Kakao tozu 420 q 9.79", 9.79)]

    winners, why = assign_cards(targets, cards)

    assert len(winners) == 1
    assert why == {}


@pytest.mark.parametrize(
    "əvvəlki,yeni,gözlənilən",
    [
        (None, "zəif", "zəif"),
        ("qiymət yoxdur", "kart tutulub", "kart tutulub"),
        ("kart tutulub", "qiymət yoxdur", "kart tutulub"),
    ],
)
def test_səbəb_ən_irəli_gedəni_saxlayır(əvvəlki, yeni, gözlənilən):
    """Məhsul bir neçə səhifədə yoxlanır; hesabatda ən informativ səbəb qalır."""
    assert better_reason(əvvəlki, yeni) == gözlənilən


def test_ambiguity_gap_sıfır_deyil():
    """Fərq yoxlaması sönsə, yaxın iki namizəddən biri təsadüfən seçilərdi."""
    assert AMBIGUITY_GAP > 0


def test_bir_məhsul_iki_kart_almır():
    """
    Bir məhsulun eyni kataloqda bir neçə qiymət sətri ola bilər. İkinci
    uyğunluq birinci faylın üstünə yazılırdı - fayl adı `p<id>.jpg` olduğu
    üçün səssizcə. Ölçüldü: 137-ci kataloqda belə 3 məhsul var.
    """
    cards = [card("Xırdalan pivə 500 ml", 1.99, 0), card("Xırdalan pivə 400 ml", 2.49, 1)]
    targets = [
        target(7, "Xırdalan pivə 500 ml 1.99", 1.99),
        target(7, "Xırdalan pivə 400 ml 2.49", 2.49),
    ]

    winners, _ = assign_cards(targets, cards)

    assert len(winners) == 1
    assert winners[0].product_id == 7
