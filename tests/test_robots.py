"""
robots.txt oxuyucusunun testləri.

ŞƏBƏKƏYƏ ÇIXMIRIQ — `RobotsRules.parse()` mətn qəbul edir. Aşağıdakı mətnlər
real saytlardan götürülüb (2026-09-08), amma test onları sabit sətir kimi
saxlayır: sayt sabah robots.txt-ini dəyişsə bizim məntiqimiz sınmamalıdır.
"""

from ingestion.robots import RobotsRules

UA = "BasketIQ-Student-Project/1.0 (educational)"

# arazmarket.az - `Allow: /` ilə `Disallow: /api/` EYNİ qrupdadır və
# `Allow` əvvəldə gəlir. Bu, "ən uzun uyğunluq" qaydasının sınaq daşıdır.
ARAZ = """\
User-Agent: *
Allow: /
Disallow: /api/
Disallow: /admin/
Disallow: /_next/
Disallow: /cart
Disallow: /checkout

Host: https://www.arazmarket.az
Sitemap: https://www.arazmarket.az/sitemap.xml
"""

# bravosupermarket.az - demək olar hər şeyə icazə verir.
BRAVO = """\
User-agent: *
Disallow: /bravo.jis.az/
Allow: /

Sitemap: https://www.bravosupermarket.az/sitemap.xml
"""

# umico.az - sorğu sətri qadağandır, amma səhifələmə açıq saxlanılıb.
UMICO = """\
User-agent: *
Disallow: /search/
Disallow: /*?*
Allow: /*?page=*
Allow: /categories/*?view=categories
"""


# ------------------------------------------------------- ən uzun uyğunluq


def test_uzun_qadaga_qisa_icazeni_ustelenir():
    """`Allow: /` əvvəldə olsa da `Disallow: /api/` qalib gəlməlidir."""
    rules = RobotsRules.parse(ARAZ, UA)
    assert rules.allows("https://www.arazmarket.az/az/categories/quru-meyveler-2")
    assert not rules.allows("https://www.arazmarket.az/api/")
    assert not rules.allows("https://www.arazmarket.az/api/products?page=2")
    assert not rules.allows("https://www.arazmarket.az/_next/data/abc.json")


def test_qadagasiz_yollar_acig_qalir():
    rules = RobotsRules.parse(ARAZ, UA)
    assert rules.allows("https://www.arazmarket.az/")
    assert rules.allows("https://www.arazmarket.az/az/products/eti-popkek-1")
    assert not rules.allows("https://www.arazmarket.az/cart")


def test_bravo_yalniz_bir_yolu_baglayir():
    rules = RobotsRules.parse(BRAVO, UA)
    assert rules.allows("https://bravosupermarket.az/special-offers/")
    assert not rules.allows("https://bravosupermarket.az/bravo.jis.az/x")


# ------------------------------------------------------- ulduz və sorğu sətri


def test_sorgu_setri_qadagan_amma_sehifeleme_acig():
    rules = RobotsRules.parse(UMICO, UA)
    assert rules.allows("https://umico.az/categories/4497-dukan")
    # `?page=` üçün açıq `Allow` var və o, `/*?*`-dan uzundur
    assert rules.allows("https://umico.az/categories/4497-dukan?page=3")
    # başqa sorğu parametri qadağan qalır
    assert not rules.allows("https://umico.az/categories/4497-dukan?sort=price")
    assert not rules.allows("https://umico.az/search/?q=sud")


def test_dollar_lovbersi_yolun_sonunu_baglayir():
    rules = RobotsRules.parse("User-agent: *\nDisallow: /account$\n", UA)
    assert not rules.allows("https://x.az/account")
    assert rules.allows("https://x.az/account/settings")


# ------------------------------------------------------- qrup seçimi


def test_bize_aid_qrup_ulduzdan_ustundur():
    text = (
        "User-agent: *\n"
        "Disallow: /\n"
        "\n"
        "User-agent: BasketIQ-Student-Project\n"
        "Allow: /\n"
    )
    rules = RobotsRules.parse(text, UA)
    assert rules.allows("https://x.az/hər-hansı")


def test_ardicil_user_agent_setirleri_eyni_qrupdur():
    text = "User-agent: alpha\nUser-agent: *\nDisallow: /gizli/\n"
    rules = RobotsRules.parse(text, UA)
    assert not rules.allows("https://x.az/gizli/fayl")
    assert rules.allows("https://x.az/açıq")


def test_bos_disallow_qadaga_deyil():
    """`Disallow:` (boş) "hər şeyə icazə" deməkdir, "hər şey qadağan" yox."""
    rules = RobotsRules.parse("User-agent: *\nDisallow:\n", UA)
    assert rules.allows("https://x.az/istənilən/yol")


def test_qayda_yoxdursa_icaze_var():
    rules = RobotsRules.parse("# boş fayl\n", UA)
    assert rules.allows("https://x.az/")


# ------------------------------------------------------- hamısı bağlı / açıq


def test_disallow_all_bayragi_her_seyi_baglayir():
    """403 cavabı üçün çağıran tərəf bu bayrağı qaldırır."""
    rules = RobotsRules(disallow_all=True)
    assert not rules.allows("https://x.az/")


def test_allow_all_bayragi_her_seyi_acir():
    """404 = robots.txt yoxdur = qadağa yoxdur."""
    rules = RobotsRules(allow_all=True)
    assert rules.allows("https://x.az/hər-nə")


def test_serh_setirleri_kecilir():
    text = "User-agent: *\n# Disallow: /tələ/\nDisallow: /real/\n"
    rules = RobotsRules.parse(text, UA)
    assert rules.allows("https://x.az/tələ/a")
    assert not rules.allows("https://x.az/real/a")
