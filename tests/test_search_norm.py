"""
AXTARIŞ NORMALLAŞDIRMASI VƏ UYĞUNLUQ PİLLƏLƏRİ (M0 + M1).

PROBLEM GÜNDƏLİKDİR: telefonda «düşbərə» yazmaq üçün altı dəfə uzun basmaq
lazımdır, adam isə «dusbere» yazır. Köhnə axtarış `LIKE '%dusbere%'` ilə heç
nə tapmırdı — məhsul bazada var, istifadəçi «yoxdur» cavabı alırdı.

BU TESTLƏRİN YARISI ƏKS İSTİQAMƏTƏ BAXIR: normallaşdırma çox genişlənsə,
«süd» sorğusu «sut», «suz», «sus» gətirər və dəqiq nəticə yalançıların
içində itər. Ona görə «sut → süd TAPMAMALIDIR» testi burada ən vaciblərdəndir.
"""

import re
from pathlib import Path

import pytest

from app.search_norm import (
    EXACT,
    FOLD_MAP,
    FUZZY,
    MIN_FUZZY_LEN,
    PREFIX,
    SUBSTRING,
    fold,
    match_score,
    token_score,
    tokens,
)

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


# ============================================================================
# M0 — FOLD
# ============================================================================


@pytest.mark.parametrize(
    "mətn,gözlənilən",
    [
        ("Düşbərə", "dusbere"),
        ("DÜŞBƏRƏ", "dusbere"),
        ("yağ", "yag"),
        ("süd", "sud"),
        ("Şəkər", "seker"),
        ("çörək", "corek"),
        ("İSTİ", "isti"),
        ("ILIQ", "iliq"),
        ("Ağ Çay", "ag cay"),
    ],
)
def test_fold_diakritikləri_atır(mətn, gözlənilən):
    assert fold(mətn) == gözlənilən


@pytest.mark.parametrize("mətn", ["Düşbərə", "İSTİ çay", "Şəkər tozu", "ILIQ SU", "yağ"])
def test_fold_uzunluğu_dəyişmir(mətn):
    """
    ƏVƏZLƏMƏ 1:1-DİR - bu, zövq məsələsi deyil, tələbdir.

    «ə» → «ae» kimi genişlənmə olsaydı, normallaşmış mətndəki mövqe orijinal
    mətndəki mövqedən sürüşərdi və uyğunluğu ekranda işıqlandırmaq üçün
    indeksləri yenidən hesablamaq lazım gələrdi. Hər belə hesablama bir hərf
    sürüşməsi ilə səhv verir.
    """
    assert len(fold(mətn)) == len(mətn)


def test_böyük_i_hərfləri_hər_iki_formada_eyni_düşür():
    """
    Azərbaycan əlifbasında «I» → «ı», «İ» → «i». Python-un `lower()`-i isə
    lokaldan asılı deyil. ƏVVƏL FOLD, SONRA KİÇİK HƏRF qaydası hər iki böyük
    hərfi ASCII «i»-yə salır - nəticə platformadan asılı olmur.
    """
    assert fold("I") == "i"
    assert fold("İ") == "i"
    assert fold("ISTI") == fold("İSTİ") == "isti"


def test_boş_giriş_boş_qaytarır():
    assert fold(None) == ""
    assert fold("") == ""
    assert tokens(None) == []


def test_tokenlərə_bölmə():
    assert tokens("Araz Süd 1 L") == ["araz", "sud", "1", "l"]
    assert tokens("kola-cola") == ["kola", "cola"]


def test_js_cədvəli_python_ilə_eynidir():
    """
    İKİ NÜSXƏ VAXTLA AYRILIR: biri yenilənir, digəri unudulur və axtarış
    brauzerdə bir cür, serverdə başqa cür işləyir. Belə fərq SƏSSİZDİR —
    hər iki tərəf «işləyir», sadəcə nəticələr uyğun gəlmir.

    `python -m tools.sync_fold_table --apply` fərqi düzəldir.
    """
    js = (STATIC / "search-norm.js").read_text(encoding="utf-8")
    blok = re.search(r"const FOLD_MAP = \{(.*?)\};", js, re.S)
    assert blok, "search-norm.js-də FOLD_MAP tapılmadı"

    js_map = dict(re.findall(r'"(.)":\s*"(.)"', blok.group(1)))
    assert js_map == FOLD_MAP, (
        "JS cədvəli Python-dan fərqlənir — "
        "`python -m tools.sync_fold_table --apply` işlət"
    )


# ============================================================================
# M1 — UYĞUNLUQ PİLLƏLƏRİ
# ============================================================================


def test_pillələr_düzgün_sıradadır():
    """Kiçik rəqəm = daha yaxşı uyğunluq. Sıra pozulsa, sıralama tərsinə dönər."""
    assert EXACT < PREFIX < SUBSTRING < FUZZY


def test_tam_bərabərlik_birinci_pillədir():
    assert token_score("sud", "milla sud") == EXACT
    assert token_score("sud", "sud") == EXACT


def test_söz_başlanğıcı_ikinci_pillədir():
    assert token_score("sud", "sudlu sirniyyat") == PREFIX


def test_söz_ortası_üçüncü_pillədir():
    """«bere» → «düşbərə»: söz ortası da tapılmalıdır."""
    assert token_score("bere", "tac dusbere") == SUBSTRING


def test_bir_hərf_səhvi_dördüncü_pillədir():
    assert token_score("dusberre", "tac dusbere", allow_fuzzy=True) == FUZZY
    assert token_score("dusbere", "tac dusberre", allow_fuzzy=True) == FUZZY   # əskik hərf
    assert token_score("dusbero", "tac dusbere", allow_fuzzy=True) == FUZZY    # dəyişmə


def test_fuzzy_qısa_sözlərdə_işləmir():
    """
    ƏSAS QORUMA. «süd» üç hərflidir və ondan bir hərf uzaqlıqda «sut», «suz»,
    «sus» var. Qısa sözdə bir hərf fərqi MƏNA fərqidir, yazı səhvi deyil.
    """
    assert token_score("sut", "milla sud", allow_fuzzy=True) is None
    assert len("sut") < MIN_FUZZY_LEN


def test_fuzzy_bağlı_olanda_işləmir():
    """Dördüncü pillə yalnız açıq şəkildə istənəndə işə düşür."""
    assert token_score("dusberre", "tac dusbere") is None


def test_iki_hərf_səhvi_qəbul_edilmir():
    assert token_score("dusberrre", "tac dusbere", allow_fuzzy=True) is None


# ------------------------------------------------------------------ VƏ məntiqi


def test_çoxsözlü_sorğu_bütün_tokenləri_tələb_edir():
    assert match_score("araz milla sud", tokens("araz sud")) is not None
    assert match_score("milla sud", tokens("araz sud")) is None


def test_ən_pis_pillə_seçilir():
    """
    «milla» dəqiq, «sudl» isə söz başlanğıcı ilə uyğun gəlirsə, nəticənin
    etibarı ZƏİF tərəfə görə qiymətləndirilməlidir - əks halda bir dəqiq söz
    bütün sətri «tam uyğunluq» kimi göstərərdi.
    """
    assert match_score("milla sudlu icki", tokens("milla sudl")) == PREFIX


def test_boş_sorğu_uyğunluq_vermir():
    assert match_score("milla sud", []) is None


# ============================================================================
# UÇDAN-UCA: real baza üzərində
# ============================================================================


@pytest.fixture
def kataloq():
    """«Tac düşbərə» və bir neçə qonşu məhsul - diakritikli adlarla."""
    import uuid

    from app.db import db_cursor

    süffiks = uuid.uuid4().hex[:6]
    with db_cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE slug = 'araz'")
        row = cur.fetchone()
        if row:
            store_id = row["id"]
        else:
            cur.execute("INSERT INTO stores (slug, name) VALUES ('araz', 'Araz')")
            store_id = cur.lastrowid

        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, status) "
            "VALUES (?, ?, 'search-test.pdf', 'parsed')",
            (store_id, uuid.uuid4().hex),
        )
        catalog_id = cur.lastrowid

        idlər = {}
        for ad, brend, kateqoriya in [
            ("düşbərə", "Tac", "quru ərzaq"),
            ("süd", "Milla", "süd məhsulları"),
            ("günəbaxan yağı", "Sola", "yağ və souslar"),
            ("şəkər tozu", None, "quru ərzaq"),
        ]:
            key = f"{ad}|{süffiks}"
            from app.search_norm import fold as _fold

            cur.execute(
                "INSERT INTO products (canonical_key, name, brand, category, group_key, name_norm) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key, ad, brend, kateqoriya, key, _fold(f"{brend or ''} {ad}".strip())),
            )
            pid = cur.lastrowid
            idlər[ad] = pid
            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price, seen_at) "
                "VALUES (?, ?, ?, 3.99, datetime('now'))",
                (pid, store_id, catalog_id),
            )
    return idlər


def _adlar(q: str) -> list[str]:
    from app.catalog import search

    return [i["label"] for i in search(q=q, limit=20)["items"]]


@pytest.mark.parametrize(
    "sorğu,gözlənilən",
    [
        ("yag", "yağı"),
        ("sud", "süd"),
        ("dusbere", "düşbərə"),
        ("DUSBERE", "düşbərə"),
        ("bere", "düşbərə"),        # söz ortası
        ("dusberre", "düşbərə"),    # bir hərf artıq
        ("düşbərə", "düşbərə"),     # əks istiqamət: diakritikli sorğu
        ("seker", "şəkər"),
    ],
)
def test_diakritiksiz_sorğu_tapır(kataloq, sorğu, gözlənilən):
    tapılanlar = _adlar(sorğu)
    assert any(gözlənilən in ad for ad in tapılanlar), (
        f"«{sorğu}» sorğusu «{gözlənilən}» tapmadı: {tapılanlar}"
    )


def test_sut_südü_tapmır(kataloq):
    """
    YALANÇI POZİTİV TESTİ. «sut» üç hərflidir - fuzzy ona toxunmur, alt sətir
    kimi də «sud» içində yoxdur. Tapsaydı, hər qısa sorğu onlarla yaxın söz
    gətirər və dəqiq nəticə itərdi.
    """
    assert not any("süd" in ad for ad in _adlar("sut"))


def test_ekranda_ad_orijinal_formada_qalır(kataloq):
    """
    Normallaşdırma YALNIZ müqayisə üçündür. Ekranda «dusbere» görünsəydi,
    sayt məhsulun adını səhv yazırmış kimi görünərdi.
    """
    tapılanlar = _adlar("dusbere")
    assert tapılanlar, "nəticə boşdur"
    assert any("Tac düşbərə" == ad for ad in tapılanlar)
    assert not any("dusbere" in ad for ad in tapılanlar)


def test_dəqiq_nəticə_varsa_fuzzy_işə_düşmür(kataloq):
    """
    «sud» sorğusu dəqiq uyğunluq tapır, ona görə yazı səhvi keçidi
    ÜMUMİYYƏTLƏ açılmır - əks halda «şəkər» kimi uzaq sözlər də siyahıya
    girərdi.
    """
    tapılanlar = _adlar("sud")
    assert any("süd" in ad for ad in tapılanlar)
    assert not any("şəkər" in ad for ad in tapılanlar)


def test_yeni_məhsul_yazılanda_axtarış_sütunu_dolur():
    """
    Sütun yazma anında dolmalıdır: boş qalsa, məhsul bazada olur, amma
    axtarışda HEÇ VAXT tapılmır - və səhv səssizdir.
    """
    import uuid

    from app.db import get_connection
    from app.models import ExtractedProduct
    from ingestion.pipeline import save_products

    key = f"axtaris|sutun|{uuid.uuid4().hex[:6]}"
    from app.db import db_cursor

    with db_cursor() as cur:
        cur.execute("SELECT id FROM stores WHERE slug = 'araz'")
        row = cur.fetchone()
        store_id = row["id"] if row else None
        if store_id is None:
            cur.execute("INSERT INTO stores (slug, name) VALUES ('araz', 'Araz')")
            store_id = cur.lastrowid
        cur.execute(
            "INSERT INTO catalogs (store_id, file_hash, file_path, status) "
            "VALUES (?, ?, 'norm.pdf', 'parsed')",
            (store_id, uuid.uuid4().hex),
        )
        catalog_id = cur.lastrowid

    save_products(
        [
            ExtractedProduct(
                name="şirin çörək",
                brand="Ağdaş",
                price=1.20,
                canonical_key=key,
                raw_line="şirin çörək 1.20",
            )
        ],
        store_id,
        catalog_id,
    )

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT name_norm FROM products WHERE canonical_key = ?", (key,)
        ).fetchone()
    finally:
        conn.close()

    assert row["name_norm"] == "agdas sirin corek"


def test_bazada_axtarış_sütunu_boş_qalmır():
    """
    İNVARİANT: hər məhsul sətrinin `name_norm` dəyəri olmalıdır.

    Sütun boş qalan sətir bazada var, axtarışda isə YOXDUR - və bunu heç bir
    xəta göstərmir. `init_db()` köhnə sətirləri doldurur, `save_products()`
    isə yeni sətirləri yazarkən doldurur; bu test hər iki yolun işlədiyini
    yoxlayır.

    REAL SƏHVDƏN ÇIXIB: `tests/test_voice.py` məhsulu birbaşa SQL ilə yazırdı
    və sütunu doldurmurdu - axtarış onu tapmırdı, səs əmri isə «tapılmadı»
    cavabı verirdi.
    """
    from app.db import get_connection, init_db

    init_db()
    conn = get_connection()
    try:
        boş = conn.execute(
            "SELECT COUNT(*) FROM products WHERE name_norm IS NULL OR name_norm = ''"
        ).fetchone()[0]
    finally:
        conn.close()

    assert boş == 0, f"{boş} məhsulun axtarış sütunu boşdur - onlar tapılmayacaq"
