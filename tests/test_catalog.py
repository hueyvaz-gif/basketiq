"""
Kataloq qatının testləri: bugünün endirimləri, «harada al», nişanlar, AI qeydi.

BU TESTLƏRİN TUTDUĞU SƏHV NÖVÜ HƏMİŞƏ EYNİDİR: heç bir xəta atmayan, amma
istifadəçiyə YANLIŞ mənzərə göstərən hallar.

    - reyestrdən kənar market (test marketləri) qiymət cədvəlinə düşür;
    - məhsulu satmayan market üçün boş sətir yaranır və «0.00» kimi oxunur;
    - «ən ucuz» nişanı ən ucuz olmayan sətirdə qalır;
    - model qiymət uydurur və qeyd inandırıcı görünür.

Hamısında səhifə «işləyir» - sadəcə yalan danışır.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from ai.product_note import build_product_facts, find_banned_claim, product_note
from app.catalog import (
    MAX_DEPTH,
    MIN_DISCOUNT_PCT,
    product_detail,
    store_page,
    todays_deals,
)
from app.db import db_cursor
from app.main import app
from app.stores import MARKETS, market_status

client = TestClient(app)


# --------------------------------------------------------------------- data


def _store(slug: str, name: str) -> int:
    """Marketi yaradır və ya mövcud olanın id-sini qaytarır."""
    with db_cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO stores (slug, name) VALUES (?, ?)", (slug, name))
        return cur.lastrowid


def _catalog(store_id: int) -> int:
    """`prices.catalog_id` NOT NULL-dur, ona görə hər qiymətə kataloq lazımdır."""
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, status) "
            "VALUES (?, ?, ?, 'parsed')",
            (store_id, uuid.uuid4().hex, "test.pdf"),
        )
        return cur.lastrowid


def _product(group_key: str, name: str, brand=None, size=None, unit=None,
             category="digər") -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO products (canonical_key, name, brand, size_value, size_unit, "
            "                      category, group_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"{group_key}|{uuid.uuid4().hex[:6]}", name, brand, size, unit,
             category, group_key),
        )
        return cur.lastrowid


def _price(product_id: int, store_id: int, price: float, old=None, unit=None) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price, old_price, "
            "                    unit_price, seen_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            (product_id, store_id, _catalog(store_id), price, old, unit),
        )


@pytest.fixture(scope="module")
def markets() -> dict[str, int]:
    """
    İki reyestr marketi + reyestrdən KƏNAR bir market.

    Kənar market qəsdən var: testlərin yarısı məhz onun cavaba düşmədiyini
    yoxlayır.
    """
    return {
        "araz": _store("araz", "Araz"),
        "bravo": _store("bravo", "Bravo"),
        "kenar": _store("kenar-market", "Kənar Market"),
    }


# ------------------------------------------------------------------ reyestr


def test_reyestr_dörd_marketdən_ibarətdir():
    """
    Tapşırıqda dörd market var. Beşincisi əlavə olunsa, «harada al» cədvəli
    istifadəçinin tanımadığı adı göstərərdi.
    """
    assert len(MARKETS) == 4
    names = {m.name for m in MARKETS}
    assert names == {"Araz Market", "Bravo Market", "Bazar Store", "Rahat Market"}



def test_datası_olan_market_şəbəkənin_başındadır(markets):
    """
    B9: ana səhifədəki market şəbəkəsində dolu marketlər öndə gəlir.

    Sıra əvvəl reyestrdən gəlirdi və TƏSADÜFƏN doğru idi (Araz və Bravo
    reyestrdə onsuz da birinci iki yerdədir). Bazar Store əvvəl dolsaydı,
    şəbəkənin ilk kartı «Tezliklə» olardı - istifadəçi ilk gördüyü kartı
    saytın ümumi vəziyyəti kimi oxuyur.
    """
    sıra = [m["available"] for m in market_status()]
    assert sıra == sorted(sıra, reverse=True), "boş market dolu marketdən əvvəl gəlir"


def test_eyni_qrupda_reyestr_sırası_qorunur(markets):
    """
    Sıralama STABİL olmalıdır: eyni vəziyyətdəki marketlər hər açılışda
    yerini dəyişsə, istifadəçi kartları əzbərləyə bilməzdi.
    """
    reyestr = [m.slug for m in MARKETS]
    dolu = [m["slug"] for m in market_status() if m["available"]]
    assert dolu == [s for s in reyestr if s in dolu]


def test_datası_olmayan_market_siyahıda_qalır(markets):
    """
    Bazar Store və Rahat Market üçün mənbə hələ yoxdur.

    Onları siyahıdan SİLMƏK olmaz: istifadəçi dörd market gözləyir və iki
    market görəndə səbəbini bilməlidir. `available: False` UI-da «Tezliklə»
    yazısına çevrilir.
    """
    status = {m["slug"]: m for m in market_status()}
    assert set(status) == {"araz", "bravo", "bazar-store", "rahat"}
    assert status["bazar-store"]["available"] is False
    assert status["rahat"]["available"] is False


def test_reyestrdən_kənar_market_təkliflərə_düşmür(markets):
    """
    Kənar market bazadadır, amma bizim dörd marketimizdən deyil.

    Bu, ən səssiz səhvdir: cədvəl doludur, rəqəmlər düzgündür, sadəcə
    istifadəçiyə vəd olunmayan market göstərilir.
    """
    pid = _product("kenar|test|1l", "kənar süd", size=1, unit="l")
    _price(pid, markets["araz"], 2.50)
    _price(pid, markets["kenar"], 1.90)  # daha ucuz - «ən ucuz» olmağa çalışır

    detail = product_detail(pid)
    stores = {o["store"] for o in detail["offers"]}
    assert stores == {"Araz Market"}, f"kənar market cavaba düşdü: {stores}"


# -------------------------------------------------------------- «harada al»


def test_məhsulu_satmayan_market_sətir_yaratmır(markets):
    """
    TAPŞIRIĞIN ƏSAS TƏLƏBİ: məhsul bütün marketlərdə yoxdursa, yalnız
    mövcud olanlar göstərilir — boş sütun, «0.00» və ya xəta YOX.
    """
    pid = _product("tek|market|test", "tək market məhsulu")
    _price(pid, markets["araz"], 3.20)

    detail = product_detail(pid)
    assert len(detail["offers"]) == 1
    assert detail["offers"][0]["store"] == "Araz Market"
    # Müqayisə də uydurulmur: ikinci qiymət yoxdursa, xülasə də yoxdur.
    assert detail["compare"] is None


def test_ən_ucuz_nişanı_ən_aşağı_qiymətdədir(markets):
    pid = _product("iki|market|test", "iki market məhsulu")
    _price(pid, markets["araz"], 4.50)
    _price(pid, markets["bravo"], 3.90)

    detail = product_detail(pid)
    best = [o for o in detail["offers"] if o["is_cheapest"]]
    assert len(best) == 1
    assert best[0]["store"] == "Bravo Market"
    assert best[0]["price"] == 3.90
    assert detail["compare"]["spread"] == 0.60


def test_təklif_tək_olanda_nişan_verilmir(markets):
    """
    «Ən ucuz» sözü müqayisə tələb edir. Tək təklifin yanında nişan qoysaq,
    istifadəçi olmayan bir müqayisənin nəticəsini görmüş olar.
    """
    pid = _product("tek|nisan|test", "tək nişan məhsulu")
    _price(pid, markets["araz"], 1.10)

    offer = product_detail(pid)["offers"][0]
    assert offer["is_cheapest"] is False
    assert offer["is_best_value"] is False


def test_ən_sərfəli_nişanı_ən_ucuzla_təkrarlanmır(markets):
    """
    Eyni məhsulun bütün təklifləri eyni ölçüdədir, yəni vahid qiyməti
    sıralaması qiymət sıralaması ilə ÜST-ÜSTƏ düşür. Belə halda ikinci nişan
    heç nə əlavə etmir - yalnız gözü yayındırır.
    """
    pid = _product("olcu|eyni|test", "eyni ölçü məhsulu", size=1, unit="kg")
    _price(pid, markets["araz"], 5.00)
    _price(pid, markets["bravo"], 6.00)

    offers = product_detail(pid)["offers"]
    assert any(o["is_cheapest"] for o in offers)
    assert not any(o["is_best_value"] for o in offers)


# ------------------------------------------------------------ ölçü variantları


def test_variant_nişanları_ölçüyə_görə_ayrılır(markets):
    """
    ƏN UCUZ ilə ƏN SƏRFƏLİ fərqli sətirlərdir:
        125 ml -> 1.39 AZN (ucuz, amma 1 L = 11.12 AZN)
        1000 ml -> 4.55 AZN (baha, amma 1 L = 4.55 AZN)
    Bu ikisini qarışdırmaq istifadəçini birbaşa yanlış seçimə aparır.
    """
    small = _product("variant|test|0.125l", "variant dondurma", brand="VarBrand",
                     size=125, unit="ml")
    big = _product("variant|test|1l", "variant dondurma", brand="VarBrand",
                   size=1000, unit="ml")
    _price(small, markets["araz"], 1.39)
    _price(big, markets["araz"], 4.55)

    variants = {v["size"]: v for v in product_detail(big)["variants"]}
    assert set(variants) == {"125 ml", "1000 ml"}

    assert variants["125 ml"]["is_cheapest"] is True
    assert variants["125 ml"]["is_best_value"] is False
    assert variants["1000 ml"]["is_cheapest"] is False
    assert variants["1000 ml"]["is_best_value"] is True


def test_variant_tək_olanda_bölmə_boş_qalır(markets):
    """Bir ölçü müqayisə deyil - UI bölməni ümumiyyətlə göstərməməlidir."""
    pid = _product("variant|tek|test", "tək variant", brand="TekBrand",
                   size=500, unit="g")
    _price(pid, markets["araz"], 2.00)
    assert product_detail(pid)["variants"] == []


# ------------------------------------------------------------------ endirimlər


def test_endirimlər_faizə_görə_düzülür(markets):
    deep = _product("endirim|derin|test", "dərin endirim")
    shallow = _product("endirim|azca|test", "azca endirim")
    _price(deep, markets["araz"], 5.00, old=10.00)      # 50%
    _price(shallow, markets["araz"], 9.00, old=10.00)   # 10%

    items = todays_deals(limit=50)["items"]
    order = [d["group_key"] for d in items]
    assert order.index("endirim|derin|test") < order.index("endirim|azca|test")


def test_ağlabatmayan_endirim_siyahıya_düşmür(markets):
    """
    90% endirim ərzaqda praktiki olaraq olmur - ya OCR səhvidir, ya uydurma
    köhnə qiymət. Süzgəc olmasaydı, siyahının BAŞINDA həmişə zibil dayanardı,
    çünki sıralama məhz faizə görədir.
    """
    pid = _product("endirim|absurd|test", "absurd endirim")
    _price(pid, markets["araz"], 1.00, old=20.00)  # 95%

    keys = {d["group_key"] for d in todays_deals(limit=100)["items"]}
    assert "endirim|absurd|test" not in keys
    assert MAX_DEPTH == pytest.approx(0.70)


def test_cüzi_endirim_siyahıya_düşmür(markets):
    pid = _product("endirim|cuzi|test", "cüzi endirim")
    _price(pid, markets["araz"], 9.90, old=10.00)  # 1%

    keys = {d["group_key"] for d in todays_deals(limit=100)["items"]}
    assert "endirim|cuzi|test" not in keys
    assert MIN_DISCOUNT_PCT == pytest.approx(3.0)


def test_hər_məhsul_siyahıda_bir_dəfədir(markets):
    """
    Eyni məhsul iki marketdə endirimdədirsə, kart TƏK olur və böyük faiz
    göstərilir. Əks halda siyahının yarısı təkrar olardı.
    """
    pid_a = _product("endirim|tekrar|test", "təkrar məhsul")
    pid_b = _product("endirim|tekrar|test", "təkrar məhsul")
    _price(pid_a, markets["araz"], 6.00, old=10.00)    # 40%
    _price(pid_b, markets["bravo"], 8.00, old=10.00)   # 20%

    items = [d for d in todays_deals(limit=100)["items"]
             if d["group_key"] == "endirim|tekrar|test"]
    assert len(items) == 1
    assert items[0]["discount_pct"] == pytest.approx(40.0)
    # Kiçik endirim itmir - kartın içindəki müqayisədə qalır.
    assert {o["store"] for o in items[0]["offers"]} == {"Araz Market", "Bravo Market"}


def test_endirim_kartında_market_müqayisəsi_var(markets):
    """
    50% endirim qonşu marketin adi qiymətindən baha ola bilər. Kart bunu
    göstərməsə, «endirim» sözü istifadəçini yanıldar.
    """
    pid_a = _product("endirim|muqayise|test", "müqayisəli məhsul")
    pid_b = _product("endirim|muqayise|test", "müqayisəli məhsul")
    _price(pid_a, markets["araz"], 5.00, old=10.00)  # endirimli
    _price(pid_b, markets["bravo"], 4.00)            # endirimsiz, AMMA ucuz

    deal = next(d for d in todays_deals(limit=100)["items"]
                if d["group_key"] == "endirim|muqayise|test")
    assert deal["compare"]["store"] == "Bravo Market"
    assert deal["compare"]["cheapest"] == 4.00


# --------------------------------------------------------------- AI qeydi


def _fake_llm(text: str):
    """`get_llm()` əvəzinə sabit cavab qaytaran zəncir halqası."""
    return RunnableLambda(lambda _: AIMessage(content=text))


def test_faktlarda_yalnız_bizim_bildiyimiz_var(markets):
    """
    Fakt bloku modelin GÖRDÜYÜ hər şeydir. Ora məhsulun dadı və ya
    keyfiyyəti haqqında sətir düşsə, model onu təkrarlamaqda haqlı olardı.
    """
    pid = _product("qeyd|fakt|test", "fakt məhsulu", size=1, unit="l")
    _price(pid, markets["araz"], 2.50)
    _price(pid, markets["bravo"], 2.90)

    facts = build_product_facts(product_detail(pid))
    assert "2.50" in facts and "2.90" in facts
    assert "Araz Market" in facts
    # Bazada olmayan mövzular fakt blokunda ola bilməz.
    for forbidden in ("dad", "keyfiyyət", "rəy", "ulduz"):
        assert forbidden not in facts.lower()


def test_qeyd_uydurma_rəy_ifadəsini_rədd_edir(markets, monkeypatch):
    """
    Model «dadlıdır» yazsa, bu, SAXTA RƏYDİR: bizdə bir dənə də müştəri rəyi
    yoxdur. Prompt bunu qadağan edir, amma promptun qadağası zəmanət deyil -
    ona görə yoxlama koddadır.
    """
    pid = _product("qeyd|rey|test", "rəy məhsulu")
    _price(pid, markets["araz"], 3.00)

    monkeypatch.setattr(
        "ai.product_note.get_llm",
        lambda **kw: _fake_llm("Bu məhsul çox dadlıdır və alıcılar bəyənir."),
    )
    result = product_note(product_detail(pid), use_cache=False)

    assert result["available"] is False
    assert "rəy" in result["reason"]
    assert result["text"] == ""


def test_qeyd_datada_olmayan_rəqəmi_rədd_edir(markets, monkeypatch):
    """
    Ən təhlükəli hallucination rəqəmdir: səhv qiymət inandırıcı görünür və
    istifadəçi onu yoxlaya bilmir.
    """
    pid = _product("qeyd|reqem|test", "rəqəm məhsulu")
    _price(pid, markets["araz"], 3.00)

    monkeypatch.setattr(
        "ai.product_note.get_llm",
        lambda **kw: _fake_llm("Bu məhsul Araz Market-də 1.23 AZN-dir."),
    )
    result = product_note(product_detail(pid), use_cache=False)

    assert result["available"] is False
    assert "1.23" in result["reason"]


def test_düzgün_qeyd_qəbul_olunur(markets, monkeypatch):
    pid = _product("qeyd|duzgun|test", "düzgün qeyd məhsulu")
    _price(pid, markets["araz"], 3.00)
    _price(pid, markets["bravo"], 3.50)

    monkeypatch.setattr(
        "ai.product_note.get_llm",
        lambda **kw: _fake_llm("Araz Market-də 3.00 AZN ilə daha ucuzdur."),
    )
    result = product_note(product_detail(pid), use_cache=False)

    assert result["available"] is True
    assert "3.00" in result["text"]
    assert result["check"]["ok"] is True


def test_model_qırılanda_səhifə_dayanmır(markets, monkeypatch):
    """
    Model əlçatmaz olanda qeyd sadəcə GƏLMİR. Səhifənin qalanı - qiymət
    cədvəli, variantlar, oxşar məhsullar - modeldən asılı deyil.
    """
    pid = _product("qeyd|qirilma|test", "qırılma məhsulu")
    _price(pid, markets["araz"], 3.00)

    def _boom(**kw):
        raise RuntimeError("model yoxdur")

    monkeypatch.setattr("ai.product_note.get_llm", _boom)
    result = product_note(product_detail(pid), use_cache=False)

    assert result["available"] is False
    assert result["text"] == ""


def test_qadağan_siyahısı_şəkilçini_də_tutur():
    """
    Azərbaycan dilində şəkilçi sözə yapışır. `\\b` ilə axtarsaq, «dadlıdır»
    tutulmazdı - yalnız «dadlı» tutulardı.
    """
    assert find_banned_claim("Məhsul dadlıdır.") == "dadlı"
    assert find_banned_claim("Alıcılar bəyənirlər.") is not None
    assert find_banned_claim("Araz Market-də 2.50 AZN-dir.") is None


# -------------------------------------------------------------- market səhifəsi


def test_hər_marketin_loqo_ünvanı_var():
    """
    Ana səhifədəki şəbəkə loqonu ünvandan çəkir. Ünvan reyestrdən gəlir -
    frontend-də ayrıca fayl adı siyahısı SAXLANILMIR, əks halda ad
    dəyişəndə iki yerdə düzəliş lazım olardı.
    """
    for market in market_status():
        assert market["logo"], f"{market['name']} üçün loqo ünvanı yoxdur"
        assert market["logo"].startswith("/static/images/")

    # Fayl adları slug-la eyni deyil: «bazar-store» -> «bazar.png».
    logos = {m["slug"]: m["logo"] for m in market_status()}
    assert logos["bazar-store"].endswith("bazar.png")


def test_market_səhifəsi_öz_məhsullarını_qaytarır(markets):
    pid = _product("market|sehife|test", "market səhifə məhsulu")
    _price(pid, markets["araz"], 7.00, old=10.00)

    data = store_page("araz")
    assert data["market"]["name"] == "Araz Market"
    keys = {d["group_key"] for d in data["deals"]}
    assert "market|sehife|test" in keys


def test_market_səhifəsində_yad_marketin_məhsulu_yoxdur(markets):
    """
    `/store/araz` yalnız Araz-ın qiymətlərini göstərməlidir. Filtr düşsə,
    səhifə yenə dolu görünər - sadəcə başqa marketin datası ilə.
    """
    pid = _product("market|yad|test", "yad market məhsulu")
    _price(pid, markets["bravo"], 2.00, old=4.00)

    keys = {d["group_key"] for d in store_page("araz")["deals"]}
    assert "market|yad|test" not in keys


def test_datası_olmayan_market_səhifəsi_açılır():
    """
    Bazar Store-un datası yoxdur, amma səhifəsi 404 VERMİR: boş siyahı və
    `available: False` ilə açılır. UI həmin bayraqdan «Tezliklə» yazır.
    Kartı kliklənməz etmək səbəbi gizlədərdi.
    """
    data = store_page("bazar-store")
    assert data is not None
    assert data["market"]["available"] is False
    assert data["deals"] == []
    assert data["products"] == []


def test_reyestrdə_olmayan_market_səhifəsi_yoxdur():
    """Kənar market bazadadır, amma bizim deyil - səhifəsi də olmamalıdır."""
    assert store_page("kenar-market") is None
    assert store_page("uydurma-market") is None


def test_api_market_səhifəsi(markets):
    assert client.get("/api/catalog/store/kenar-market").status_code == 404

    res = client.get("/api/catalog/store/araz")
    assert res.status_code == 200
    body = res.json()
    assert body["market"]["slug"] == "araz"

    # Datası olmayan market 200 verir - vəziyyəti səhifə izah edir.
    soon = client.get("/api/catalog/store/rahat")
    assert soon.status_code == 200
    assert soon.json()["market"]["available"] is False


def test_market_səhifəsi_html_qaytarır():
    res = client.get("/store/araz")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


# ------------------------------------------- kenar market bütün ekranlardan
#
# BU BÖLMƏ REAL SƏHVDƏN ÇIXIB. Trolley ekranları dörd marketlə qurulandan
# sonra da səbət cavabı kənar marketi «ən çox əhatə» kimi göstərirdi: köhnə
# bazadakı BÜTÜN marketləri götürürdü. Yəni istifadəçi ana səhifədə dörd
# market görür, cavabda isə beşinci markete yönləndirilirdi — və heç bir
# test bunu tutmurdu, çünki hər iki tərəf ayrılıqda «işləyirdi».


def _basket_with(product_id: int) -> int:
    """Müvəqqəti səbət yaradır və məhsulu ora salır."""
    with db_cursor() as cur:
        cur.execute("INSERT INTO baskets (name) VALUES ('kenar-market-test')")
        basket_id = cur.lastrowid
        cur.execute(
            "INSERT INTO basket_items (basket_id, product_id, qty) VALUES (?, ?, 1)",
            (basket_id, product_id),
        )
    return basket_id


def test_kənar_market_səbət_müqayisəsində_görünmür(markets):
    """Səbət cavabı yalnız dörd marketi tanımalıdır."""
    pid_araz = _product("sebet|kenar|test", "səbət kənar məhsulu")
    pid_kenar = _product("sebet|kenar|test", "səbət kənar məhsulu")
    _price(pid_araz, markets["araz"], 5.00)
    _price(pid_kenar, markets["kenar"], 1.00)  # ən ucuz - qalib olmağa çalışır

    basket_id = _basket_with(pid_araz)
    data = client.get(f"/api/basket/compare?basket_id={basket_id}").json()

    stores = {s["store"] for s in data["stores"]}
    assert "Kənar Market" not in stores, f"kənar market müqayisəyə düşdü: {stores}"
    assert stores <= {m.name for m in MARKETS}

    # Məhsulun qiymətləri də yalnız reyestr marketlərindən gəlir.
    item = next(i for i in data["items"] if i["product_id"] == pid_araz)
    assert item["available_in"] == 1


def test_müqayisədə_market_adı_reyestrdən_gəlir(markets):
    """
    Bazada market «Araz» yazılıb, məhsul isə «Araz Market» adlanır.

    İki ad iki problem yaradır: istifadəçi eyni marketi iki cür görür və
    market rəngi (o, ADDAN hesablanır) səhifədən səhifəyə dəyişir.
    """
    pid = _product("sebet|ad|test", "ad testi məhsulu")
    _price(pid, markets["araz"], 2.00)

    basket_id = _basket_with(pid)
    data = client.get(f"/api/basket/compare?basket_id={basket_id}").json()

    names = {s["store"] for s in data["stores"]}
    assert "Araz Market" in names
    assert "Araz" not in names, "bazadakı xam ad cavaba düşür"


def test_kənar_market_endirim_yoxlamasında_görünmür(markets):
    """«Şübhəli endirim» siyahısı da yalnız bizim marketlərə baxır."""
    pid = _product("endirim|kenar|test", "endirim kənar məhsulu")
    _price(pid, markets["kenar"], 4.00, old=8.00)

    from app.analytics import discount_summary

    stores = {row["store"] for row in discount_summary(limit=200)["items"]}
    assert "Kənar Market" not in stores, f"kənar market endirim siyahısına düşdü: {stores}"


def test_kənar_market_qiymət_tarixçəsində_görünmür(markets):
    """Qrafik dörd marketin xəttini çəkir — beşincisini yox."""
    pid_araz = _product("tarixce|kenar|test", "tarixçə kənar məhsulu")
    pid_kenar = _product("tarixce|kenar|test", "tarixçə kənar məhsulu")
    _price(pid_araz, markets["araz"], 3.00)
    _price(pid_kenar, markets["kenar"], 2.00)

    from app.analytics import price_history

    history = price_history("tarixce|kenar|test")
    assert "Kənar Market" not in set(history["stores"])
    assert "Araz Market" in set(history["stores"])


# ------------------------------------------------------------------- API


def test_api_məhsul_tapılmayanda_404_verir():
    assert client.get("/api/catalog/product/99999999").status_code == 404


def test_api_məhsul_səhifəsi_bütün_bölmələri_qaytarır(markets):
    pid = _product("api|test|1kg", "api məhsulu", brand="ApiBrand",
                   size=1, unit="kg", category="quru ərzaq")
    _price(pid, markets["araz"], 4.00)

    data = client.get(f"/api/catalog/product/{pid}").json()
    for key in ("product", "offers", "compare", "variants", "similar",
                "same_brand", "markets"):
        assert key in data, f"cavabda «{key}» yoxdur"
    # Dörd marketin statusu HƏMİŞƏ gəlir - «Tezliklə» yazısı ondan qidalanır.
    assert len(data["markets"]) == 4


def test_api_məhsul_səhifəsi_html_qaytarır():
    """`/product/{id}` ünvanı paylaşıla bilən səhifədir, JSON deyil."""
    res = client.get("/product/1")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    # Keşlənməməlidir - qalan statik fayllarla eyni qayda.
    assert "no-cache" in res.headers.get("cache-control", "")
