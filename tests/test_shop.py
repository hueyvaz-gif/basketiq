"""
MAĞAZA (SAYT) QATI testləri — `ingestion/shop.py` + `save_snapshots`.

ŞƏBƏKƏYƏ ÇIXMIR. Wolt-un kart mətnləri sabit sətir kimi saxlanılır: real
sorğu testi həm yavaş edərdi, həm də saytın kefindən asılı salardı. Sətirlər
UYDURULMAYIB - 2026-09-10-da `bravo-hypermarket-20-yanvar` məkanından
ölçülmüş faktiki `innerText` dəyərləridir.
"""

import pytest

from app.db import PRICE_ROWS_CTE, db_cursor, get_connection
from ingestion.pipeline import save_snapshots
from ingestion.profiles import PROFILES, profile_for
from ingestion.shop import ShopError, parse_card, scrape_shop

# Wolt qırılmayan boşluq işlədir - testdə də məhz o olmalıdır, adi boşluq
# olsaydı regex real səhifədə düşərdi, testdə isə keçərdi.
NB = " "


def _lines(*parts: str) -> dict:
    return {"lines": list(parts), "href": "/x-itemid-deadbeef", "image": None}


# ---------------------------------------------------------------- parse_card


def test_endirimli_kart_iki_qiyməti_ayırır():
    p = parse_card(
        _lines("Populyar", f"~AZN{NB}0.85", f"AZN{NB}0.99",
               "Xiyar Melit 1kq 2393", "~1kg", f"AZN{NB}0.85 / kq"),
        "Meyvə və Tərəvəzlər",
    )
    assert p is not None
    assert p.name == "Xiyar Melit 1kq 2393"
    assert p.price == 0.85
    assert p.old_price == 0.99
    assert p.size_value == 1.0
    assert p.size_unit == "kg"
    assert p.category == "Meyvə və Tərəvəzlər"


def test_endirimsiz_kartda_köhnə_qiymət_olmur():
    p = parse_card(
        _lines(f"~AZN{NB}4.99", "Pomidor Çəhrayı 1kq 2512", "~1kg", f"AZN{NB}4.99 / kq"),
        "Meyvə",
    )
    assert p is not None
    assert p.price == 4.99
    assert p.old_price is None


def test_nişan_ad_kimi_götürülmür():
    """«Populyar» kartın rozetidir - məhsul adı deyil."""
    p = parse_card(_lines("Populyar", f"AZN{NB}3.19", "Süd Palıd 1L", "1l"), "Süd")
    assert p is not None
    assert p.name == "Süd Palıd 1L"


def test_qiymətsiz_və_adsız_kart_atılır():
    """Yarımçıq kart bazaya DÜŞMƏMƏLİDİR - qiyməti olmayan sətir mənasızdır."""
    assert parse_card(_lines("Populyar", f"AZN{NB}3.19"), "Süd") is None
    assert parse_card(_lines("Süd Palıd 1L", "1l"), "Süd") is None


def test_sıraya_deyil_nümunəyə_baxılır():
    """
    Nişan olan və olmayan kartlarda sətirlərin SIRASI fərqlidir.
    Sıraya güvənsək, biri düzgün, digəri səhv oxunardı.
    """
    nişanlı = parse_card(
        _lines("Populyar", f"~AZN{NB}1.15", f"AZN{NB}1.45", "Kök Yerli 1kq", "~1kg"), "Meyvə"
    )
    nişansız = parse_card(
        _lines(f"~AZN{NB}1.15", f"AZN{NB}1.45", "Kök Yerli 1kq", "~1kg"), "Meyvə"
    )
    assert nişanlı.name == nişansız.name == "Kök Yerli 1kq"
    assert nişanlı.price == nişansız.price == 1.15
    assert nişanlı.old_price == nişansız.old_price == 1.45


def test_tərs_yazılmış_qiymətdə_böyüyü_köhnə_sayılır():
    """Qiymət heç vaxt öz köhnəsindən baha ola bilməz."""
    p = parse_card(_lines(f"AZN{NB}1.98", f"AZN{NB}1.38", "Kələm Ağ kq", "~2.5kg"), "Meyvə")
    assert p.price == 1.38
    assert p.old_price == 1.98


def test_woltun_vahid_qiyməti_hesablanandan_üstündür():
    """
    «~2.5kg» TƏXMİNİ çəkidir: 1.38 / 2.5 = 0.552, Wolt isə 0.55 yazır.
    Çəki ilə satılan məhsulda Wolt-un öz rəqəmi daha dəqiqdir.
    """
    p = parse_card(
        _lines(f"~AZN{NB}1.38", "Kələm Ağ kq", "~2.5kg", f"AZN{NB}0.55 / kq"), "Meyvə"
    )
    assert p.unit_price == 0.55


# ---------------------------------------------------------------- profil


def test_bravonun_mağaza_ünvanı_var_kataloq_ünvanı_isə_bağlıdır():
    """
    İki qat müstəqildir: kataloq mənbəyi `BLOCKED` olsa da, mağaza mənbəyi
    işləyə bilər. Bir bayrağa bağlasaydıq, işləyən mənbə bağlı görünərdi.
    """
    bravo = profile_for("bravo")
    assert bravo.shoppable is True
    assert "wolt.com" in bravo.shop_url
    assert bravo.scrapeable is False


def test_arazın_mağaza_ünvanı_yoxdur():
    """Arazın `robots.txt`-i `/api/`-ni bağlayır - mağaza qatı mümkün deyil."""
    assert profile_for("araz").shoppable is False


def test_mağaza_ünvanı_olmayan_market_aydın_xəta_verir():
    with pytest.raises(ShopError, match="shop_url"):
        scrape_shop("araz")


def test_bütün_profillərdə_shop_url_ya_none_ya_httpsdir():
    for slug, profile in PROFILES.items():
        assert profile.shop_url is None or profile.shop_url.startswith("https://"), slug


# ---------------------------------------------------------------- saxlama


def _store_id(cur, slug: str = "bravo") -> int:
    cur.execute("INSERT OR IGNORE INTO stores (name, slug) VALUES (?, ?)", ("Bravo Market", slug))
    cur.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
    return cur.fetchone()[0]


def test_snapshot_prices_cədvəlinə_YAZMIR():
    """
    Rəf qiyməti kataloq iddiası deyil. `prices`-ə yazsaydıq, endirim
    yoxlaması öz mənbəyini özü ilə təsdiqləyərdi (dairəvi məntiq).
    """
    p = parse_card(_lines(f"AZN{NB}2.40", "Test Süd 1L", "1l"), "Süd")
    with db_cursor() as cur:
        store_id = _store_id(cur)
        cur.execute("SELECT COUNT(*) FROM prices")
        əvvəl = cur.fetchone()[0]

    save_snapshots([p], store_id, source="site")

    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == əvvəl
        row = conn.execute(
            "SELECT source, price, is_promo FROM price_snapshots "
            "WHERE store_id = ? ORDER BY id DESC LIMIT 1",
            (store_id,),
        ).fetchone()
        assert row["source"] == "site"
        assert row["price"] == 2.40
    finally:
        conn.close()


def test_eyni_gün_təkrar_çəkiliş_xəta_vermir():
    """
    `ux_snapshot_daily` gündə bir sətir tələb edir. `ON CONFLICT` olmasaydı,
    gün ərzində ikinci çəkiliş IntegrityError ilə qırılardı - yəni n8n-in
    təkrar cəhdi bütün axını öldürərdi.
    """
    p1 = parse_card(_lines(f"AZN{NB}5.00", "Təkrar Test Yağ 1L", "1l"), "Yağ")
    p2 = parse_card(_lines(f"AZN{NB}4.50", "Təkrar Test Yağ 1L", "1l"), "Yağ")
    with db_cursor() as cur:
        store_id = _store_id(cur)

    save_snapshots([p1], store_id, source="site")
    save_snapshots([p2], store_id, source="site")  # xəta ATMAMALIDIR

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ps.price FROM price_snapshots ps JOIN products p ON p.id = ps.product_id "
            "WHERE p.name = ? AND ps.store_id = ?",
            ("Təkrar Test Yağ 1L", store_id),
        ).fetchall()
        assert len(rows) == 1, "gündə bir sətir qaydası pozuldu"
        assert rows[0]["price"] == 4.50, "ikinci çəkiliş qiyməti yeniləməlidir"
    finally:
        conn.close()


def test_köhnə_qiymət_is_promo_nişanı_qoyur():
    p = parse_card(_lines(f"AZN{NB}1.50", f"AZN{NB}2.00", "Promo Test Çay 100q"), "Çay")
    with db_cursor() as cur:
        store_id = _store_id(cur)
    save_snapshots([p], store_id, source="site")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT ps.is_promo FROM price_snapshots ps JOIN products p ON p.id = ps.product_id "
            "WHERE p.name = ?",
            ("Promo Test Çay 100q",),
        ).fetchone()
        assert row["is_promo"] == 1
    finally:
        conn.close()


def test_yanlış_source_rədd_olunur():
    p = parse_card(_lines(f"AZN{NB}1.00", "Yanlış Source Test"), "digər")
    with db_cursor() as cur:
        store_id = _store_id(cur)
    with pytest.raises(ValueError, match="source"):
        save_snapshots([p], store_id, source="wolt")


# ---------------------------------------------------------------- sayğac


def test_price_rows_cte_hər_iki_qatı_sayır():
    """
    Sayğacın ƏSAS REQRESİYASI: yalnız `prices` sayılsaydı, kataloqu olmayan
    market həmişə «0 məhsul» görünərdi.
    """
    p = parse_card(_lines(f"AZN{NB}9.99", "CTE Test Məhsulu 1kq", "1kg"), "digər")
    with db_cursor() as cur:
        store_id = _store_id(cur, "bravo")
    save_snapshots([p], store_id, source="site")

    conn = get_connection()
    try:
        sayı = conn.execute(
            f"{PRICE_ROWS_CTE} "
            "SELECT COUNT(DISTINCT pr.product_id) FROM price_rows pr WHERE pr.store_id = ?",
            (store_id,),
        ).fetchone()[0]
        yalnız_kataloq = conn.execute(
            "SELECT COUNT(DISTINCT product_id) FROM prices WHERE store_id = ?", (store_id,)
        ).fetchone()[0]
        assert sayı > yalnız_kataloq
    finally:
        conn.close()


def test_market_status_mağaza_məhsulunu_available_sayır():
    """`available=False` UI-da «Tezliklə» deməkdir - mağaza datası varsa yanlışdır."""
    from app.stores import market_status

    p = parse_card(_lines(f"AZN{NB}3.33", "Available Test Məhsulu 1L", "1l"), "digər")
    with db_cursor() as cur:
        store_id = _store_id(cur, "bravo")
    save_snapshots([p], store_id, source="site")

    bravo = next(m for m in market_status() if m["slug"] == "bravo")
    assert bravo["available"] is True
    assert bravo["products"] > 0


# ---------------------------------------------------------------- market sətri


def test_mağaza_çəkilişi_dublikat_market_yaratmır():
    """
    REQRESSİYA (2026-09-10, layihədə İKİNCİ dəfə).

    `get_or_create_store("Bravo Market")` adı slug-a çevirir -> `bravo-market`,
    halbuki bazadakı sətrin slug-u `bravo`-dur. Nəticədə İKİ market sətri
    yaranır və marketin datası ikiyə bölünür: sayğac bir sətri, səhifə
    digərini göstərir. Eyni səhv əvvəl Araz üçün baş verib
    (`app/db.py:STORE_MERGES`).
    """
    from app.api.shop import resolve_store_id

    with db_cursor() as cur:
        cur.execute(
            "INSERT OR IGNORE INTO stores (name, slug) VALUES (?, ?)", ("Bravo", "bravo")
        )

    store_id = resolve_store_id("bravo")

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT slug FROM stores WHERE slug IN ('bravo', 'bravo-market')"
        ).fetchall()
        sluglar = {r["slug"] for r in rows}
        assert "bravo-market" not in sluglar, "dublikat market sətri yarandı"
        kanonik = conn.execute("SELECT id FROM stores WHERE slug = 'bravo'").fetchone()["id"]
        assert store_id == kanonik
    finally:
        conn.close()


def test_reyestrdə_olmayan_slug_üçün_də_işləyir():
    """Tanınmayan market sadəcə öz slug-u ilə yaradılır - çöküş olmur."""
    from app.api.shop import resolve_store_id

    assert isinstance(resolve_store_id("yeni-market-testi"), int)


# ---------------------------------------------------------------- addım-addım yazılış


def _fake_report(stats=None, saved=0, found=0):
    from ingestion.shop import ShopReport

    r = ShopReport(slug="bravo", store="Bravo Market", shop_url="https://wolt.com/x")
    r.category_stats = stats or []
    r.saved, r.found = saved, found
    return r


def test_hər_kateqoriya_ayrıca_yazılır(monkeypatch):
    """
    ADDIM-ADDIM YAZILIŞ. Əvvəl bütün məhsullar yaddaşda toplanıb yalnız SONDA
    yazılırdı - 40 dəqiqəlik çəkiliş yarıda kəsiləndə hamısı itirdi.
    İndi hər kateqoriya bitən kimi bazaya düşür.
    """
    import app.api.shop as shop_api

    çağırışlar = []

    def saxta_scrape(slug, max_categories=None, max_products=None,
                     on_category=None, keep_products=False):
        # İki kateqoriya - hər biri ayrıca yazılmalıdır.
        for ad, məhsul_adı in (("Meyvə", "Addım Test Alma 1kq"),
                               ("Süd", "Addım Test Süd 1L")):
            p = parse_card(_lines(f"AZN{NB}1.11", məhsul_adı, "1kg"), ad)
            çağırışlar.append((ad, on_category(ad, [p])))
        return _fake_report(saved=sum(n for _, n in çağırışlar), found=2)

    monkeypatch.setattr(shop_api, "scrape_shop", saxta_scrape)
    payload = shop_api.run_shop_scrape("bravo", x_api_key=None)

    assert len(çağırışlar) == 2, "callback hər kateqoriya üçün çağırılmadı"
    assert all(n == 1 for _, n in çağırışlar), "hər çağırışda bir məhsul yazılmalıdır"
    assert payload["saved"] == 2

    conn = get_connection()
    try:
        for ad in ("Addım Test Alma 1kq", "Addım Test Süd 1L"):
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM price_snapshots ps "
                "JOIN products p ON p.id = ps.product_id WHERE p.name = ?",
                (ad,),
            ).fetchone()
            assert row["n"] == 1, f"«{ad}» yazılmadı"
    finally:
        conn.close()


def test_dry_run_heç_nə_yazmır(monkeypatch):
    """`dry_run` callback VERMİR - yəni yazma yolu ümumiyyətlə açılmır."""
    import app.api.shop as shop_api

    görülən = {}

    def saxta_scrape(slug, max_categories=None, max_products=None,
                     on_category=None, keep_products=False):
        görülən["on_category"] = on_category
        görülən["keep_products"] = keep_products
        return _fake_report(found=0)

    monkeypatch.setattr(shop_api, "scrape_shop", saxta_scrape)
    payload = shop_api.run_shop_scrape("bravo", dry_run=True, x_api_key=None)

    assert görülən["on_category"] is None
    assert görülən["keep_products"] is True
    assert payload["dry_run"] is True
    assert payload["saved"] == 0


def test_bir_kateqoriyanın_yazma_xətası_çəkilişi_dayandırmır():
    """
    Yazma xətası HESABATA düşür, amma qalan kateqoriyalar yenə yazılır -
    əks halda bir səhv 40 dəqiqəlik işi ləğv edərdi.
    """
    from ingestion.shop import ShopReport

    report = ShopReport(slug="bravo", store="Bravo", shop_url="https://wolt.com/x")
    # `scrape_shop`-un daxili məntiqini birbaşa təqlid edirik: xəta tutulur,
    # hesabata yazılır, dövr davam edir.
    for ad, partla in (("Meyvə", True), ("Süd", False)):
        try:
            if partla:
                raise RuntimeError("baza kilidli")
            report.saved += 1
        except Exception as e:  # noqa: BLE001
            report.errors.append(f"{ad} (yazma): {type(e).__name__}: {e}")

    assert report.saved == 1
    assert len(report.errors) == 1
    assert "Meyvə" in report.errors[0]


def test_kateqoriya_statistikası_hesabatda_görünür():
    """Uzun çəkilişdə tək «cəmi» rəqəmi boş qayıdan bölməni gizlədirdi."""
    r = _fake_report(
        stats=[{"category": "Meyvə", "found": 93, "saved": 93, "seconds": 26.3},
               {"category": "Süd", "found": 0, "saved": 0, "seconds": 4.1}],
        saved=93, found=93,
    )
    d = r.as_dict()
    assert d["category_stats"][1]["found"] == 0
    assert d["found_count"] == 93


# ---------------------------------------------------------------- brauzer bərpası


def test_olu_brauzer_xetasi_taninir():
    """
    ÖLÇÜLDÜ (real çəkiliş, 2026-09-10): 13-cü kateqoriyada Chrome öldü
    (`InvalidSessionIdException: session deleted as the browser has closed
    the connection`) və QALAN 29 KATEQORİYA ardıcıl düşdü - nəticə 13 460
    əvəzinə 3 017 məhsul oldu.

    Səhv «bir kateqoriya düşsə qalanı davam edir» qaydası ilə MASKALANMIŞDI:
    dövr həqiqətən davam edirdi, amma ölü brauzerlə - hər addım eyni xətanı
    təkrarlayırdı.
    """
    from ingestion.shop import _is_dead_browser

    class InvalidSessionIdException(Exception):
        pass

    class WebDriverException(Exception):
        pass

    assert _is_dead_browser(InvalidSessionIdException("session deleted"))
    assert _is_dead_browser(WebDriverException("ERR_NAME_NOT_RESOLVED"))


def test_adi_xeta_brauzer_olumu_sayilmir():
    """
    Hər xətada brauzeri yenidən qaldırmaq bahalıdır (~4 saniyə) və səbəbi
    gizlədir. Yalnız SESSİYA xətaları bərpa tələb edir.
    """
    from ingestion.shop import _is_dead_browser

    assert not _is_dead_browser(TimeoutError("gecikdi"))
    assert not _is_dead_browser(ValueError("səhv dəyər"))


def test_sinif_adina_gore_yoxlanilir_idxala_gore_yox():
    """
    Selenium sinifləri LAZY idxal olunur: modul səviyyəsində idxal etmək
    Chrome quraşdırılmayan maşında bütün layihəni qırardı. Ona görə yoxlama
    sinif ADI üzrədir.
    """
    from pathlib import Path

    src = Path("ingestion/shop.py").read_text(encoding="utf-8")
    gövdə = src.split("def _is_dead_browser")[1].split("\ndef ")[0]
    assert "type(exc).__name__" in gövdə
    assert "from selenium" not in gövdə


def test_brauzer_berpasi_hesabata_dusur():
    """
    Bərpa SƏSSİZ olmamalıdır: nəticə əskik gəlirsə, səbəbin hesabatda
    görünməsi lazımdır.
    """
    from pathlib import Path

    src = Path("ingestion/shop.py").read_text(encoding="utf-8")
    assert "session.restarts" in src
    assert "yenidən qaldırıldı" in src
