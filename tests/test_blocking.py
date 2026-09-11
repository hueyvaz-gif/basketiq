"""
Bloklama testləri — hansı cütlərin ümumiyyətlə müqayisə olunduğu.

Bloklama səhv qurulsa iki cür uduzuruq: ya real uyğunluq heç vaxt müqayisə
olunmur (səssiz itki), ya da hər şey hər şeylə müqayisə olunur və
`/api/match/candidates` serveri kilidləyir.
"""

from ai.blocking import blocking_keys, candidate_pairs, known_brands

BRAVO, ARAZ, RAHAT = 2, 15, 1266


def product(name, key, brand=None, stores=None):
    p = {"name": name, "canonical_key": key, "match_key": key, "brand": brand}
    if stores is not None:
        p["stores"] = set(stores)
    return p


class TestBlockingKeys:
    def test_brend_sahesi_varsa_brend_bloku(self):
        p = product("süd", "milla|sud|1l", brand="Milla")
        assert blocking_keys(p, set()) == {"b:milla"}

    def test_bravo_brendi_luget_ile_addan_tapilir(self):
        p = product("Milla Süd 2 5% 1l", "milla|sud|1l")
        assert blocking_keys(p, {"milla"}) == {"b:milla"}

    def test_brendsiz_mehsul_soz_prefiksi_ile(self):
        p = product("toyuq yumurtası", "toyuq|yumurtasi|10pcs")
        assert blocking_keys(p, set()) == {"w:toy", "w:yum"}

    def test_olcu_tokeni_blok_deyil(self):
        p = product("su", "sirab|su|1.5l")
        assert blocking_keys(p, set()) == {"w:sir"}

    def test_luget_yalniz_brend_sahesinden_qurulur(self):
        products = [product("süd", "k1", brand="Milla"), product("Milla Süd 1l", "k2")]
        assert known_brands(products) == {"milla"}


class TestCandidatePairs:
    def test_bravo_ve_araz_eyni_brend_blokunda_gorusur(self):
        products = [
            product("süd", "milla|sud|1l", brand="Milla", stores=[ARAZ]),
            product("Milla Süd 2 5% 1l", "milla|sud|1l", stores=[BRAVO]),
        ]
        assert list(candidate_pairs(products)) == [(0, 1)]

    def test_eyni_marketin_mehsullari_muqayise_olunmur(self):
        """Bravo bir məhsulu rəfində iki dəfə satmır — iki sətir = iki məhsul."""
        products = [
            product("Milla Qatıq 1.5% 450qr", "milla|qatiq|0.45kg", stores=[BRAVO]),
            product("Milla Qatıq 3.5% 500qr", "milla|qatiq|0.5kg", stores=[BRAVO]),
            product("qatıq", "milla|qatiq|0.45kg", brand="Milla", stores=[ARAZ]),
        ]
        pairs = set(candidate_pairs(products))
        assert (0, 1) not in pairs
        assert pairs == {(0, 2), (1, 2)}

    def test_ferqli_brendler_muqayise_olunmur(self):
        """«süd» ortaqdır, amma Milla ≠ Atena — əvvəl bu cüt LLM-ə gedirdi."""
        products = [
            product("süd", "milla|sud|1l", brand="Milla", stores=[ARAZ]),
            product("süd", "atena|sud|1l", brand="Atena", stores=[BRAVO]),
        ]
        assert list(candidate_pairs(products)) == []

    def test_sekilcili_brendsiz_sozler_eyni_blokda(self):
        """yumurta / yumurtası — ilk 3 hərf eynidir, uyğunluq itmir."""
        products = [
            product("yumurta", "yumurta|10pcs", stores=[ARAZ]),
            product("Kənd Yumurtası 10əd.", "kend|yumurtasi|10pcs", stores=[BRAVO]),
        ]
        assert list(candidate_pairs(products)) == [(0, 1)]

    def test_qiymeti_olmayan_mehsul_atilir(self):
        products = [
            product("süd", "milla|sud|1l", brand="Milla", stores=[]),
            product("Milla Süd 1l", "milla|sud|1l", stores=[BRAVO]),
        ]
        assert list(candidate_pairs(products)) == []

    def test_market_bilinmirse_cut_buraxilir(self):
        """Köhnə çağırışlar `stores` göndərmir — onlar əvvəlki kimi işləməlidir."""
        products = [
            product("günəbaxan yağı", "gunebaxan|sola|yagi|1.8l", brand="Sola"),
            product("günəbaxan yağ", "gunebaxan|sola|yag|1.8l", brand="Sola"),
        ]
        assert list(candidate_pairs(products)) == [(0, 1)]

    def test_hər_cut_bir_defe(self):
        """Brendsiz iki məhsul bir neçə ortaq blokda ola bilər — cüt təkrarlanmır."""
        products = [
            product("toyuq yumurtası", "toyuq|yumurtasi", stores=[ARAZ]),
            product("toyuq yumurtası", "toyuq|yumurtasi|10pcs", stores=[RAHAT]),
        ]
        assert list(candidate_pairs(products)) == [(0, 1)]

    def test_boyuk_eyni_market_bloku_cut_yaratmir(self):
        """1 000 Bravo məhsulu + 1 kataloq məhsulu -> 1 000 cüt, 500 min yox."""
        products = [
            product(f"Milla Məhsul {i}", f"milla|mehsul{i}", stores=[BRAVO]) for i in range(1000)
        ]
        products.append(product("süd", "milla|sud|1l", brand="Milla", stores=[ARAZ]))
        assert sum(1 for _ in candidate_pairs(products)) == 1000
