"""
OXŞAR MƏHSULLAR (P3) — «oxşar» sözü yalan olmasın.

ƏVVƏLKİ QAYDA TƏK ŞƏRTDƏN İBARƏT İDİ: eyni kateqoriya. Kateqoriya isə geniş
qabdır — «təmizlik və gigiyena» qabında 41 məhsul var: diş məcunu, pişik
tualeti, uşaq bezi. Nəticədə südün altında salfet görünürdü.

BU TESTLƏRİN TUTDUĞU SƏHV GÖZLƏ SEÇİLMİR: bölmə dolu görünür, kartlar
düzgün çəkilir, qiymətlər doğrudur. Yalnız MƏZMUN yalandır — və istifadəçi
ona inanır, çünki başlıqda «Oxşar məhsullar» yazılıb.
"""

import pytest

from app.similar import (
    MIN_MATCHES,
    MIN_SCORE,
    comparable_text,
    normalize,
    pick_similar,
    score,
)


def m(name, brand=None, group_key=None, **əlavə):
    return {"name": name, "brand": brand, "group_key": group_key or name, **əlavə}


# ------------------------------------------------------------- normalizasiya


def test_ölçü_və_dayaq_sözlər_atılır():
    """
    «1 l süd» ilə «1 l qatıq» ortaq «1 l» tokeninə görə oxşar sayılsaydı,
    ölçü məhsulu ƏVƏZ edərdi - bütün bir litrliklər bir-birinə oxşayardı.
    """
    assert normalize("1 l süd") == ["süd"]
    assert normalize("500 q un və şəkər") == ["un", "şəkər"]


def test_boş_ad_sıfır_bal_verir():
    assert score(m(""), m("süd")) == 0.0
    assert normalize(None) == []


# --------------------------------------------------------------------- bal


def test_eyni_ad_ən_yüksək_baldır():
    assert score(m("süd"), m("süd", group_key="sud-2")) == pytest.approx(1.0, abs=0.2)


def test_ortaq_söz_güclü_siqnaldır():
    """«şokolad» sözünü paylaşan iki məhsul praktiki olaraq həmişə oxşardır."""
    assert score(m("şokolad"), m("şokolad batonçuğu")) >= MIN_SCORE


def test_əlaqəsiz_məhsullar_hədddən_uzaqdır():
    """
    ÖLÇÜLDÜ (real data): belə cütlərin balı 0.00-0.11 aralığındadır, yəni
    0.40 həddinə yaxın da deyil.
    """
    for a, b in [
        ("süd məhsulu", "kərə yağı"),
        ("salfet", "pivə"),
        ("pişik yemi", "diş macunu"),
    ]:
        assert score(m(a), m(b)) < 0.2, f"«{a}» ilə «{b}» oxşar sayılır"


def test_brend_tək_başına_kifayət_deyil():
    """
    «Sola yağ» ilə «Sola mayonez» eyni brenddir, eyni məhsul deyil. Brend
    çəkisi 0.2-dir: tək başına həddi keçə bilmir.
    """
    bal = score(m("yağ", brand="Sola"), m("mayonez", brand="Sola", group_key="mayonez"))
    assert bal < MIN_SCORE


def test_brend_oxşarlığı_gücləndirir():
    """Eyni brend + ortaq söz: brendsizdən yüksək olmalıdır."""
    brendli = score(
        m("qatıq", brand="Milla"), m("qatıq içkisi", brand="Milla", group_key="q2")
    )
    brendsiz = score(m("qatıq"), m("qatıq içkisi", group_key="q2"))
    assert brendli > brendsiz


# ------------------------------------------------------------------ seçim


def test_dörddən_az_uyğunluq_bölməni_gizlədir():
    """
    ƏSAS QAYDA. İki zəif kartla dolu bölmə «bunlar oxşardır» iddiasıdır.
    Boş siyahı isə heç nə iddia etmir - bölmə sadəcə çəkilmir.
    """
    məhsul = m("şokolad")
    namizədlər = [m("şokolad batonçuğu", group_key="a"), m("şokoladlı peçenye", group_key="b")]
    assert pick_similar(məhsul, namizədlər) == []


def test_dörd_uyğunluq_bölməni_açır():
    məhsul = m("şokolad")
    namizədlər = [m(f"şokolad {i}", group_key=f"k{i}") for i in range(4)]
    assert len(pick_similar(məhsul, namizədlər)) == 4


def test_zəif_namizədlər_süzülür():
    """
    Dörd yaxşı uyğunluq varsa belə, zəiflər siyahıya QOŞULMUR - «say
    tamamlamaq» üçün əlaqəsiz kart göstərmək qadağandır.
    """
    məhsul = m("şokolad")
    namizədlər = [m(f"şokolad {i}", group_key=f"k{i}") for i in range(4)]
    namizədlər += [m("salfet", group_key="z1"), m("pişik yemi", group_key="z2")]

    nəticə = pick_similar(məhsul, namizədlər)
    adlar = {c["name"] for c in nəticə}
    assert "salfet" not in adlar and "pişik yemi" not in adlar


def test_ən_oxşar_əvvəldə_gəlir():
    məhsul = m("şokolad")
    namizədlər = [
        m("şokoladlı qanfet", group_key="a"),
        m("şokolad", group_key="b"),
        m("şokolad batonçuğu", group_key="c"),
        m("isti şokolad", group_key="d"),
    ]
    nəticə = pick_similar(məhsul, namizədlər)
    assert nəticə[0]["name"] == "şokolad"


def test_eyni_qrup_oxşar_sayılmır():
    """
    Eyni məhsulun başqa ölçüsü ayrıca «Ölçülər» bölməsindədir. Burada
    təkrar göstərmək siyahını doldurar, məlumat əlavə etməz.
    """
    məhsul = m("süd", group_key="milla|sud")
    namizədlər = [m("süd", group_key="milla|sud") for _ in range(6)]
    assert pick_similar(məhsul, namizədlər) == []


# ---------------------------------------------------------- kart formatı


def test_kart_sətirləri_də_müqayisə_oluna_bilir():
    """
    REAL SƏHVDƏN ÇIXIB. Bazadan gələn sətirdə `name`, kart sətirlərində isə
    yalnız `label` (brend + ad) var. Funksiya `name` gözlədiyi üçün bütün
    kartlar boş mətn verirdi, bal sıfır çıxırdı və bölmə HEÇ VAXT görünmürdü.
    Səhv səssiz idi: bölmənin gizlənməsi onsuz da mümkün haldır.
    """
    kart = {"label": "Milla süd", "brand": "Milla", "group_key": "milla|sud"}
    assert comparable_text(kart) == "süd"
    assert score(m("süd"), kart) >= MIN_SCORE


def test_brend_iki_dəfə_sayılmır():
    """
    `label`-dan brend çıxarılır: saxlasaydıq, eyni brendin iki fərqli məhsulu
    həm ortaq söz, həm brend üzrə bal toplayardı.
    """
    a = {"label": "Sola günəbaxan yağı", "brand": "Sola", "group_key": "a"}
    b = {"label": "Sola mayonez", "brand": "Sola", "group_key": "b"}
    assert score(a, b) < MIN_SCORE


# ------------------------------------------------------------- real data


def test_uçdan_uca_yalnız_oxşarlar_gəlir():
    """
    UÇDAN-UCA: SQL namizədləri, `pick_similar` qərarı verir, `product_detail`
    onu cavaba qoyur. Ayrı-ayrı funksiyaların testi bu zənciri yoxlamır -
    məsələn kart sətirlərinin `name` deyil, `label` daşıması səhvi məhz
    burada üzə çıxmışdı.

    Səhnə: eyni kateqoriyada DÖRD şokolad + İKİ əlaqəsiz məhsul.
    Gözlənilən: dörd şokolad gəlir, əlaqəsizlər GƏLMİR.
    """
    import uuid

    from app.catalog import product_detail
    from app.db import db_cursor

    kateqoriya = "şirniyyat"
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
            "VALUES (?, ?, 'similar-test.pdf', 'parsed')",
            (store_id, uuid.uuid4().hex),
        )
        catalog_id = cur.lastrowid

        idlər = {}
        adlar = [
            ("şokolad", "Nestle"),
            ("şokolad batonçuğu", "Ulduz"),
            ("şokoladlı qanfet", None),
            ("isti şokolad", None),
            # BEŞİNCİ şokolad qəsdəndir: subyektin özü namizəd deyil, yəni
            # dörd uyğunluq üçün beş şokolad lazımdır.
            ("şokoladlı peçenye", None),
            ("kartof çipsi", None),      # əlaqəsiz
            ("saqqız", None),            # əlaqəsiz
        ]
        for ad, brend in adlar:
            key = f"{ad.replace(' ', '-')}|{süffiks}"
            cur.execute(
                "INSERT INTO products (canonical_key, name, brand, group_key, category) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, ad, brend, key, kateqoriya),
            )
            pid = cur.lastrowid
            idlər[ad] = pid
            cur.execute(
                "INSERT INTO prices (product_id, store_id, catalog_id, price, seen_at) "
                "VALUES (?, ?, ?, 2.50, datetime('now'))",
                (pid, store_id, catalog_id),
            )

    data = product_detail(idlər["şokolad"])
    adlar = {k["label"] for k in data["similar"]}

    assert len(data["similar"]) >= MIN_MATCHES, "oxşar bölməsi açılmadı"
    assert "kartof çipsi" not in adlar and "saqqız" not in adlar
    for kart in data["similar"]:
        assert kart["category"] == kateqoriya
        assert score(dict(data["product"]), kart) >= MIN_SCORE
