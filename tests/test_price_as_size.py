"""
Qiymətin ölçü kimi köçürülməsi (`ingestion.pipeline.price_reused_as_size`).

REAL SƏHVDƏN ÇIXIB: sətirdə ölçü yazılmayanda model əlindəki yeganə rəqəmi -
qiyməti - ölçü sahəsinə qoyurdu. Ölçüldü (137-ci kataloq, 74 ölçülü sətir):
üç sətirdə ölçü qiymətə bərabər idi və hər üçündə `unit_price` TAM 1.0 çıxırdı.

Niyə bu, kosmetik deyil? «Ən sərfəli» sıralaması məhz `unit_price` üzrədir.
«1 litri 1 manat» kataloqdakı hər şeydən ucuz görünür, yəni saxta təklif
siyahının BAŞINA keçir - istifadəçi olmayan endirimə yönləndirilir.
"""

import pytest

from app.models import ProductAttributes
from ingestion.cleaner import CleanLine
from ingestion.pipeline import build_products, price_reused_as_size


def line(raw: str, price: float, old_price: float | None = None) -> CleanLine:
    return CleanLine(raw=raw, text=raw, price=price, old_price=old_price)


@pytest.mark.parametrize(
    "raw,price,size",
    [
        ("cay mi 1.25", 1.25, 1.25),                        # real sətir
        ("Persil Уи toz 1.35", 1.35, 1.35),                 # real sətir
        ("Bloom Ağardıcı vasitə (limon) 0.85", 0.85, 0.85),  # real sətir
    ],
)
def test_qiymet_olcu_kimi_kocurulubse_tutulur(raw, price, size):
    assert price_reused_as_size(line(raw, price), size)


def test_reqem_iki_defe_yazilibsa_olcu_REALDIR():
    """
    «1.5 L ... 1.50 ₼» - ölçü ilə qiymət təsadüfən üst-üstə düşür.
    Rəqəm sətirdə iki dəfə yazılıb, deməli ölçü uydurma deyil.
    """
    assert not price_reused_as_size(line("Sirab su 1.5 L 1.50", 1.5), 1.5)


def test_qiymetden_ferqli_olcuye_toxunulmur():
    assert not price_reused_as_size(line("Tuc Kreker 100 q 1.69", 1.69), 100.0)


def test_olcusuz_setir_problem_deyil():
    assert not price_reused_as_size(line("Zabava 3.19", 3.19), None)


def test_kohne_qiymet_de_yoxlanilir():
    assert price_reused_as_size(line("Sabun 4.90", 3.20, old_price=4.90), 4.90)


def test_mehsul_atilmir_yalniz_olcu_atilir():
    """
    Qiymət realdır - onu itirmək olmaz. Yalnız ölçü (və ondan hesablanan
    vahid qiyməti) düşür.
    """
    attrs = ProductAttributes(
        name="çay", brand=None, size_value=1.25, size_unit="l", category="içkilər"
    )

    products, skipped = build_products([line("cay mi 1.25", 1.25)], [attrs])

    assert skipped == 0
    assert len(products) == 1
    product = products[0]
    assert product.price == 1.25, "qiymət saxlanılmalıdır"
    assert product.size_value is None and product.size_unit is None
    assert product.unit_price is None, "saxta «1 litri 1 manat» hesablanmamalıdır"


def test_duz_olcu_saxlanilir():
    attrs = ProductAttributes(
        name="kreker", brand="Tuc", size_value=100.0, size_unit="g", category="şirniyyat"
    )

    products, _ = build_products([line("Tuc Kreker 100 q 1.69", 1.69)], [attrs])

    assert products[0].size_value == 100.0
    assert products[0].unit_price is not None
