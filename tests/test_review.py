"""
Karantin növbəsi — nişanlanmış sətirlərin admin baxışı (`app/review.py`).

NİYƏ AYRICA TEST FAYLI? `test_quality.py` HƏDLƏRİ yoxlayır (nə nişanlanır),
bu fayl isə NİŞANDAN SONRAKI HƏYATI: sətir adminə görünürmü, təsdiqdən sonra
ekrana qayıdırmı və qərar davamlıdırmı.

ƏSAS RİSK BURADADIR: təsdiq «unudulan» olsa, admin eyni sətri hər həftə
yenidən buraxmalı olardı və növbə heç vaxt boşalmazdı. Ona görə testlərin
yarısı məhz qərarın YAŞAMASINI yoxlayır.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.catalog import todays_deals
from app.db import db_cursor, get_connection
from app.main import app
from app.review import REVIEWED, approve_price, flagged_prices
from ingestion.quality import FLAG_DEEP_DISCOUNT, FLAG_UNIT_OUTLIER

client = TestClient(app)


# --------------------------------------------------------------------- data


@pytest.fixture
def market() -> int:
    with db_cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE slug = 'araz'")
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO stores (slug, name) VALUES ('araz', 'Araz')")
        return cur.lastrowid


def _sətir(store_id: int, flags, price: float = 4.00, old: float | None = 10.00) -> tuple[int, str]:
    """Bir qiymət sətri yaradır; `flags` bazadakı xam dəyərdir. -> (price_id, group_key)"""
    key = f"review|{uuid.uuid4().hex[:8]}"
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, status) "
            "VALUES (?, ?, 'review-test.pdf', 'parsed')",
            (store_id, uuid.uuid4().hex),
        )
        catalog_id = cur.lastrowid
        cur.execute(
            "INSERT INTO products (canonical_key, name, group_key) VALUES (?, ?, ?)",
            (key, "növbə məhsulu", key),
        )
        product_id = cur.lastrowid
        cur.execute(
            "INSERT INTO prices (product_id, store_id, catalog_id, price, old_price, "
            "                    raw_line, flags, seen_at) "
            "VALUES (?, ?, ?, ?, ?, 'xam sətir 4.00', ?, datetime('now'))",
            (product_id, store_id, catalog_id, price, old, flags),
        )
        return cur.lastrowid, key


def _flags(price_id: int):
    conn = get_connection()
    try:
        return conn.execute("SELECT flags FROM prices WHERE id = ?", (price_id,)).fetchone()["flags"]
    finally:
        conn.close()


# ------------------------------------------------------------------- növbə


def test_növbədə_yalnız_nişanlı_sətirlər_görünür(market):
    """
    Üç vəziyyət var və yalnız biri baxış tələb edir. Süzgəc səhv olsa,
    admin 195 təmiz sətrin arasında 7 şübhəlini axtarmalı olardı.
    """
    nişanlı, _ = _sətir(market, json.dumps([FLAG_DEEP_DISCOUNT]))
    təmiz, _ = _sətir(market, None)
    baxılmış, _ = _sətir(market, REVIEWED)

    növbə = {item["price_id"] for item in flagged_prices(limit=200)["items"]}
    assert nişanlı in növbə
    assert təmiz not in növbə
    assert baxılmış not in növbə, "təsdiqlənmiş sətir növbəyə qayıdıb"


def test_növbə_səbəbi_və_xam_sətri_daşıyır(market):
    """
    Admin «niyə?» sualına cavab tapmalıdır. Xam OCR sətri olmasa, qərar
    yalnız hissə əsaslanardı: rəqəm doğrudur, yoxsa kataloqda başqa cür
    yazılıb — bunu ancaq mənbə sətri göstərir.
    """
    price_id, _ = _sətir(market, json.dumps([FLAG_DEEP_DISCOUNT, FLAG_UNIT_OUTLIER]))

    item = next(i for i in flagged_prices(limit=200)["items"] if i["price_id"] == price_id)
    assert item["flags"] == [FLAG_DEEP_DISCOUNT, FLAG_UNIT_OUTLIER]
    assert item["raw_line"] == "xam sətir 4.00"
    assert item["discount_pct"] == 60          # 10.00 -> 4.00
    assert item["store"] == "Araz"


def test_zədəli_bayraq_dəyəri_növbəni_qırmır(market):
    """
    `flags` sütunu mətndir: əl ilə yazılmış SQL, yarımçıq köçürmə və ya köhnə
    format oraya JSON olmayan dəyər sala bilər. Növbə bir sətir üzündən
    tamamilə açılmasa, admin BÜTÜN datanı itirər — ona görə zədəli dəyər
    sadəcə boş siyahı sayılır.
    """
    price_id, _ = _sətir(market, "bu JSON deyil")
    item = next(i for i in flagged_prices(limit=200)["items"] if i["price_id"] == price_id)
    assert item["flags"] == []


def test_ümumi_say_limitdən_asılı_deyil(market):
    """Siyahı kəsilir, rəqəm kəsilmir: admin nə qədər iş qaldığını görməlidir."""
    for _ in range(3):
        _sətir(market, json.dumps([FLAG_DEEP_DISCOUNT]))

    nəticə = flagged_prices(limit=1)
    assert len(nəticə["items"]) == 1
    assert nəticə["total"] >= 3


# ------------------------------------------------------------------ təsdiq


def test_təsdiq_sətri_ekrana_qaytarır(market):
    """Karantindən çıxan sətir «bugünün endirimləri» siyahısına qayıtmalıdır."""
    price_id, key = _sətir(market, json.dumps([FLAG_DEEP_DISCOUNT]))
    assert key not in {d["group_key"] for d in todays_deals(limit=200)["items"]}

    assert approve_price(price_id) is True
    assert key in {d["group_key"] for d in todays_deals(limit=200)["items"]}


def test_təsdiq_NULL_yox_REVIEWED_yazır(market):
    """
    Fərq görünməz, amma nəticəsi böyükdür: NULL «hələ yoxlanmayıb» deməkdir və
    `tools/flag_prices.py` növbəti qaçışda həmin sətri YENİDƏN nişanlayardı.
    `REVIEWED` isə insan qərarını daşıyır.
    """
    price_id, _ = _sətir(market, json.dumps([FLAG_DEEP_DISCOUNT]))
    approve_price(price_id)
    assert _flags(price_id) == REVIEWED
    assert _flags(price_id) is not None


def test_təsdiqlənmiş_sətir_yenidən_nişanlanmır(market):
    """
    Qərarın DAVAMLILIĞI. `collect()` bütün bazanı yenidən qiymətləndirir;
    təsdiqlənmiş sətri ora buraxsaq, admin eyni işi hər qaçışdan sonra
    təkrarlayardı və növbə heç vaxt boşalmazdı.
    """
    from tools.flag_prices import collect

    price_id, _ = _sətir(market, json.dumps([FLAG_DEEP_DISCOUNT]), price=1.00, old=20.00)
    approve_price(price_id)

    nəticə, _ = collect()
    assert price_id not in {pid for pid, _ in nəticə}, "təsdiq geri qaytarıldı"


def test_təsdiqlənməmiş_şübhəli_sətir_yenidən_nişanlanır(market):
    """
    Əvvəlki testin əksi: guard çox geniş olsaydı, HEÇ NƏ nişanlanmazdı və
    yoxlama səssizcə sönərdi.
    """
    from tools.flag_prices import collect

    price_id, _ = _sətir(market, None, price=1.00, old=20.00)   # 95% — dərin

    nəticə, _ = collect()
    flags = dict(nəticə).get(price_id)
    assert flags == [FLAG_DEEP_DISCOUNT]


def test_iki_dəfə_təsdiq_ikinci_dəfə_işləmir(market):
    """İkinci çağırış «görüləsi iş yoxdur» deməkdir — UI onu 404 kimi göstərir."""
    price_id, _ = _sətir(market, json.dumps([FLAG_DEEP_DISCOUNT]))
    assert approve_price(price_id) is True
    assert approve_price(price_id) is False


# ---------------------------------------------------------------- endpoint


def test_endpoint_növbəni_qaytarır(market):
    _sətir(market, json.dumps([FLAG_DEEP_DISCOUNT]))
    res = client.get("/api/review/flagged")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert {"price_id", "product", "store", "flags", "raw_line"} <= set(data["items"][0])


def test_endpoint_təsdiqi_yazır(market):
    price_id, _ = _sətir(market, json.dumps([FLAG_DEEP_DISCOUNT]))
    res = client.post(f"/api/review/flagged/{price_id}/approve")
    assert res.status_code == 200
    assert _flags(price_id) == REVIEWED


def test_olmayan_sətir_404_verir():
    assert client.post("/api/review/flagged/99999999/approve").status_code == 404
