"""
Market rənginin SƏSSİZ müqaviləsi (`app/static/store-colors.js`).

Bu bölmədəki hər səhv eyni cür davranır: səhifə açılır, qrafik çəkilir, konsol
təmiz qalır — sadəcə rəng yalan danışır. İki hal var:

  1. rəng SIRAYA bağlanır. `app/api/basket.py` marketləri səbət cəminə görə
     çeşidləyir, yəni səbətə bir məhsul əlavə edən kimi sıra dəyişir. Rəng
     sıradan asılı olsa, istifadəçinin yadda saxladığı «Bravo = göy» əlaqəsi
     hər əlavədən sonra pozulur — heç bir yerdə xəta olmadan.
  2. iki market EYNİ rəngə düşür. Trend qrafikində leqenda var; iki eyni nöqtə
     leqendanı mənasız edir, amma qrafik yenə də «işləyir».

Ona görə əsas iddialar STATİK oxumaqla deyil, JS-i həqiqətən `node`-da işlədib
yoxlanılır. `node` yoxdursa test KEÇİLİR — sükutla uğurlu sayılmır.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
SOURCE = STATIC / "store-colors.js"

client = TestClient(app)

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node tapılmadı")

# Bazadakı real market adları (`Test Market` və `Test Scrape Market` seed/scrape
# testlərindən gəlir). Təmiz djb2 hash bu altılığa cəmi 3 fərqli xana verirdi.
REAL_STORES = [
    "Test Market",
    "Bravo",
    "Araz",
    "OBA",
    "Araz Market",
    "Test Scrape Market",
]

# `store-colors.js`-i HƏR ssenari üçün yenidən qiymətləndirir ki, bir
# ssenarinin qeydiyyatı digərinə sızmasın.
DRIVER = """
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
const scenarios = JSON.parse(process.argv[3]);
const out = scenarios.map((names) => {
  (0, eval)(src);
  const SC = globalThis.StoreColors;
  SC.note(names);
  const row = {};
  for (const n of names) row[n] = { slot: SC.slot(n), css: SC.cssVar(n) };
  return row;
});
console.log(JSON.stringify(out));
"""


def strip_comments(source: str) -> str:
    """
    Şərhləri atır — iddialar KODA baxmalıdır, şərhdəki izaha yox.

    Blok şərhi çoxsətirlidir (`re.S`), sətir şərhi isə deyil: `//.*`-ə `re.S`
    versək, ilk `//` faylın sonuna qədər hər şeyi udar.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//.*", "", source)


def run_js(scenarios: list[list[str]], tmp_path: Path) -> list[dict]:
    driver = tmp_path / "driver.js"
    driver.write_text(DRIVER, encoding="utf-8")
    proc = subprocess.run(
        [NODE, str(driver), str(SOURCE), json.dumps(scenarios, ensure_ascii=False)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, f"node xətası: {proc.stderr}"
    return json.loads(proc.stdout)


# ----------------------------------------------------------------- tək mənbə


def test_rəng_məntiqi_yalnız_bir_faylda_var():
    """
    İki reyestr = iki həqiqət.

    Əvvəl `app.js` API sırası, `analytics.js` isə əlifba sırası ilə öz Map-ini
    doldururdu; nəticədə eyni market cədvəldə bir, qrafikdə başqa rəngdə
    görünürdü. Heç bir test düşmürdü, çünki hər iki fayl ayrılıqda «işləyirdi».
    """
    for name in ["app.js", "analytics.js"]:
        code = strip_comments((STATIC / name).read_text(encoding="utf-8"))
        assert "5381" not in code, f"{name} hash-i öz içində təkrarlayır"
        assert not re.search(r"storeColor(Index|s)\s*=", code), (
            f"{name} ayrıca rəng reyestri saxlayır"
        )
        assert "StoreColors" in code, f"{name} ümumi mənbəni çağırmır"


def test_hər_iki_fayl_eyni_funksiyanı_çağırır():
    """`app.js` CSS dəyişəni, `analytics.js` xana nömrəsi alır — mənbə birdir."""
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    analytics_js = (STATIC / "analytics.js").read_text(encoding="utf-8")
    assert "StoreColors.cssVar(" in app_js
    assert "StoreColors.slot(" in analytics_js


def test_xana_hesablanması_sıradan_asılı_deyil():
    """
    Statik qoruyucu: `Map.size`, massiv indeksi və ya gəlmə sayğacı xanaya
    çevrilməməlidir. Məhz bu, B2-nin ilkin səbəbi idi.
    """
    code = strip_comments(SOURCE.read_text(encoding="utf-8"))
    assert not re.search(r"\.size\s*%", code), "xana Map ölçüsündən hesablanır"
    assert "indexOf" not in code and "findIndex" not in code, "xana massiv indeksindən gəlir"
    # Əlifba sırası locale-dən asılı olmamalıdır: `localeCompare` brauzerə görə
    # dəyişir və eyni data fərqli rəng verər.
    assert "localeCompare" not in code


def test_index_html_də_yüklənmə_sırası_doğrudur():
    """
    `store-colors.js` hər iki istifadəçidən ƏVVƏL yüklənməlidir. Sonra
    yüklənsə `StoreColors` təyin olunmamış olur: `analytics.js` səssizcə
    accent rənginə düşür (hamı eyni mavi), `app.js` isə qırılır.
    """
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    order = re.findall(r'<script src="/static/([\w.-]+)"', html)
    assert "store-colors.js" in order, "store-colors.js index.html-ə qoşulmayıb"
    first = order.index("store-colors.js")
    assert first < order.index("app.js")
    assert first < order.index("analytics.js")


def test_html_dəki_bütün_lokal_skriptlər_serverdən_gəlir():
    """
    Adı dəyişən fayl 404 verir və səhifə YARIM işləyir. `<script>` 404-ü
    konsoldan başqa heç yerdə görünmür.
    """
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for src in re.findall(r'<script src="(/static/[\w.-]+)"', html):
        assert client.get(src).status_code == 200, f"{src} tapılmadı"


# ------------------------------------------------------- həqiqi icra (node)


@needs_node
def test_sıra_dəyişəndə_rəng_dəyişmir(tmp_path):
    """
    Eyni market DƏSTİ fərqli sıralarla verildikdə hər market eyni xananı
    almalıdır. `basket.py:221` sıranı qiymətə görə qurur — sıra hər səbət
    dəyişikliyində fərqlidir.
    """
    orders = [
        REAL_STORES,
        list(reversed(REAL_STORES)),
        sorted(REAL_STORES),
        [REAL_STORES[i] for i in (3, 0, 5, 1, 4, 2)],
    ]
    results = run_js(orders, tmp_path)
    base = {n: v["slot"] for n, v in results[0].items()}
    for order, row in zip(orders[1:], results[1:]):
        got = {n: v["slot"] for n, v in row.items()}
        assert got == base, f"sıra {order} fərqli xana verdi: {got} != {base}"


@needs_node
def test_altı_market_altı_fərqli_xana_alır(tmp_path):
    """
    Toqquşma leqendanı öldürür. 6 xana var, 6 market var — üst-üstə düşməməlidir.

    Ölçmə: təmiz djb2 hash bu altılığa 3 fərqli xana verirdi.
    """
    (row,) = run_js([REAL_STORES], tmp_path)
    slots = [row[n]["slot"] for n in REAL_STORES]
    assert len(set(slots)) == 6, f"toqquşma: {dict(zip(REAL_STORES, slots))}"
    assert set(slots) == {0, 1, 2, 3, 4, 5}


@needs_node
def test_ixtiyari_altılıqlarda_da_toqquşma_yoxdur(tmp_path):
    """
    Yuxarıdakı test yalnız BİZİM adlara baxır — funksiyanı həmin altılığa
    uydurmaq mümkündür. Bu test isə əlaqəsiz adlarla eyni zəmanəti tələb edir.
    """
    scenarios = [
        [f"Market {i}" for i in range(6)],
        ["A", "B", "C", "D", "E", "F"],
        ["Şəki", "Gəncə", "Bakı", "Sumqayıt", "Quba", "Lənkəran"],
        ["Neptun", "Rahat", "Bazarstore", "Favorit", "Grandmart", "Kontinental"],
    ]
    for names, row in zip(scenarios, run_js(scenarios, tmp_path)):
        slots = [row[n]["slot"] for n in names]
        assert len(set(slots)) == 6, f"toqquşma: {dict(zip(names, slots))}"


@needs_node
def test_css_dəyişəni_xana_ilə_uyğundur(tmp_path):
    """
    `app.js` CSS dəyişəni, `analytics.js` isə massiv indeksi işlədir. İkisi
    sürüşsə, eyni market cədvəldə bir, qrafikdə başqa rəngdə görünər — yenə
    heç bir xəta olmadan.
    """
    (row,) = run_js([REAL_STORES], tmp_path)
    for name, value in row.items():
        assert value["css"] == f"var(--store-{value['slot'] + 1})", name
        assert 1 <= value["slot"] + 1 <= 6


@needs_node
def test_qeyd_olunmamış_ad_da_xana_alır(tmp_path):
    """
    `note()` çağırılmasa belə `slot()` etibarlı xana verməlidir — `undefined`
    qayıtsa CSS `var(--store-NaN)` olar və nöqtə RƏNGSİZ qalar (səhifə işləyir,
    market kimliyi itir).
    """
    (row,) = run_js([["Yeni Market"]], tmp_path)
    value = row["Yeni Market"]
    assert isinstance(value["slot"], int) and 0 <= value["slot"] < 6
    assert value["css"] == f"var(--store-{value['slot'] + 1})"
