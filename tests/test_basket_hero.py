"""
«SƏBƏTİNİZ HARADA UCUZDUR?» bloku — tam və natamam səbətlərin ayrılması.

ƏSAS TƏLƏ (brauzerdə görüldü 2026-09-10): tam və natamam səbətlər EYNİ
OXDA idi. Natamam səbətin cəmi kiçikdir, çünki çatışmayan məhsul sayılmır -
yəni onun zolağı QISA, deməli gözlə «daha ucuz» görünürdü:

    Araz  6.14 ₼  (süd + düyü)  -> uzun zolaq
    Bravo 1.89 ₼  (yalnız süd)  -> qısa zolaq = «ən ucuz»?

Ştrixli fon «natamam» demək istəyirdi, amma ZOLAĞIN UZUNLUĞU ayrı bir şey
deyirdi və göz rəqəmdən əvvəl uzunluğu oxuyur.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from tests.test_basket import add


def read_static(name: str) -> str:
    return (Path("app/static") / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------- backend


def _compare(client, basket_id):
    return client.get(f"/api/basket/compare?basket_id={basket_id}").json()


def test_ucuz_plan_mehsul_uzre_bolgunu_qaytarir(empty_basket, sample_data):
    """
    «0.16 ₼ qənaət» rəqəminin haradan gəldiyi izah olunmalıdır. Bunun üçün
    hər məhsulun HANSI marketdən götürüldüyü lazımdır - əks halda UI yalnız
    yekun rəqəmi göstərə bilir və istifadəçinin ona inanmaq üçün əsası olmur.
    """
    with TestClient(app) as client:
        add(client, empty_basket, sample_data["sud"])
        add(client, empty_basket, sample_data["duyu"])
        data = _compare(client, empty_basket)

    ucuz = data["cheapest"]
    assert "assignments" in ucuz, "məhsul üzrə bölgü yoxdur"
    assert len(ucuz["assignments"]) == 2
    for a in ucuz["assignments"]:
        assert {"label", "store", "price", "qty"} <= set(a)
        assert a["price"] > 0
        assert a["store"], "market adı boşdur"


def test_bolgunun_cemi_planin_cemine_beraberdir(empty_basket, sample_data):
    """Bölgü UI üçün ayrıca hesablanmır - yekun rəqəmlə uzlaşmalıdır."""
    with TestClient(app) as client:
        add(client, empty_basket, sample_data["sud"])
        add(client, empty_basket, sample_data["duyu"])
        data = _compare(client, empty_basket)

    ucuz = data["cheapest"]
    cəm = sum(a["price"] * (a["qty"] or 1) for a in ucuz["assignments"])
    assert abs(cəm - ucuz["total"]) < 0.02, f"bölgü {cəm}, plan {ucuz['total']}"
    # Süd Bravodan (1.89), düyü Arazdan (3.15) -> 5.04
    marketlər = {a["label"]: a["store"] for a in ucuz["assignments"]}
    assert marketlər["süd"] == "Bravo Market"
    assert marketlər["düyü"] == "Araz Market"


def test_natamam_market_qalib_elan_edilmir(empty_basket, sample_data):
    """
    `best` YALNIZ tam səbətdən seçilir. «çay» yalnız Arazdadır, ona görə
    Bravonun səbəti natamamdır - cəmi kiçik olsa da qalib ola bilməz.
    """
    with TestClient(app) as client:
        add(client, empty_basket, sample_data["sud"])
        add(client, empty_basket, sample_data["cay"])
        data = _compare(client, empty_basket)

    assert data["best"]["complete"] is True
    assert data["best"]["store"] == "Araz Market"

    bravo = next(s for s in data["stores"] if s["store"] == "Bravo Market")
    assert bravo["complete"] is False
    assert bravo["total"] < data["best"]["total"], (
        "test datası düzgün deyil - natamam cəm daha kiçik olmalıdır"
    )


def test_tek_mehsulluq_sebetde_de_isleyir(empty_basket, sample_data):
    """Qəbul kriteriyası: 1 və 4 məhsulluq səbətlərdə də düzgün işləməlidir."""
    with TestClient(app) as client:
        add(client, empty_basket, sample_data["sud"])
        data = _compare(client, empty_basket)

    assert len(data["cheapest"]["assignments"]) == 1
    assert data["cheapest"]["assignments"][0]["store"] == "Bravo Market"
    # Tək məhsulda bölünmüş alış qənaət VERMİR - iki rəqəm bərabərdir.
    assert abs(data["best"]["total"] - data["cheapest"]["total"]) < 0.005


# ---------------------------------------------------------------- frontend


def test_zolaq_yalniz_tam_sebetlere_cekilir():
    js = read_static("app.js")
    gövdə = js.split("function renderBars")[1].split("\nfunction ")[0]
    assert "s.complete && s.covered > 0" in gövdə, "tam səbətlər ayrılmır"
    # Natamam sətirdə `bar-fill` OLMAMALIDIR.
    natamam = gövdə.split("const partialRows")[1].split("const completeBlock")[0]
    assert "bar-fill" not in natamam, "natamam səbətə zolaq çəkilir"
    assert "bar-track" not in natamam


def test_miqyas_yalniz_tam_sebetlere_gore_qurulur():
    """
    Natamam cəm miqyasa girsəydi, o, miqyası aşağı çəkib bütün zolaqları
    uzadardı - yəni müqayisə yenidən yanlış olardı.
    """
    js = read_static("app.js")
    gövdə = js.split("function renderBars")[1].split("\nfunction ")[0]
    assert "Math.max(...complete.map((s) => s.total), 0.01)" in gövdə


def test_natamamin_sebebi_yazilir():
    """Ştrixli/passiv sətir izahsız qalmamalıdır."""
    js = read_static("app.js")
    assert "bars.partialWhy" in js
    assert "bar-missing" in js, "çatışmayan məhsulun adı göstərilmir"


def test_hero_reqemi_izah_olunur():
    """«6.14 ₼» rəqəminin bütün məhsulların cəmi olduğu deyilməlidir."""
    js = read_static("app.js")
    assert "answer.allItems" in js
    assert "answer.cheapestFull" in js


def test_bolunmus_alis_hesabi_gosterilir():
    js = read_static("app.js")
    assert "answer.splitItem" in js, "məhsul üzrə sətirlər yoxdur"
    assert "answer.splitSum" in js, "yekun cəm sətri yoxdur"
    assert "c.assignments" in js


def test_tek_tam_sebet_halinda_xeberdarliq_var():
    """
    Tam səbəti bir market satırsa, «ən ucuz» sözü müqayisə iddiası kimi
    oxunmamalıdır - qarşılaşdırılacaq ikinci namizəd yoxdur.
    """
    js = read_static("app.js")
    assert "answer.onlyOneComplete" in js
    assert "complete.length === 1" in js


def test_butun_yeni_acarlar_lugetdedir():
    i18n = read_static("i18n.js")
    for açar in (
        "answer.allItems", "answer.cheapestFull", "answer.onlyOneComplete",
        "answer.splitHead", "answer.splitItem", "answer.splitSum",
        "bars.completeHead", "bars.partialHead", "bars.partialWhy", "bars.noComplete",
    ):
        assert f'"{açar}"' in i18n, f"{açar} lüğətdə yoxdur"
        # Üç dilin hamısı olmalıdır
        blok = i18n.split(f'"{açar}"')[1][:300]
        for dil in ("az:", "en:", "ru:"):
            assert dil in blok, f"{açar}: {dil} tərcüməsi yoxdur"


def test_natamam_setirde_metn_kesilmir():
    """
    BRAUZERDƏ GÖRÜLDÜ: «Yalnız 1/2 məhsul v…» və «Mastero basmati dü…» -
    izah sətri məhz izah edən yerdə qırılırdı. Səbəb: ad sütunu tam səbət
    üçün dar (150px) idi, natamam sətirdə isə zolaq olmadığı üçün həmin
    hədd yalnız mətni kəsirdi.
    """
    css = read_static("style.css")
    blok = css.split(".bar-row.is-partial .bar-name > span")[1].split("}")[0]
    assert "white-space: normal" in blok
    assert "overflow: visible" in blok
