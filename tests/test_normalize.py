"""
Normalizasiya testləri — deterministik məntiq, LLM yoxdur.

Bu funksiyalar bütün müqayisənin təməlidir: unit_price səhv olsa,
dashboard yanlış marketi "ən ucuz" göstərər və heç kim səbəbini anlamaz.
"""

from ingestion.normalize import canonical_key, size_token, to_base, unit_price


class TestToBase:
    def test_qram_kiloqrama_cevrilir(self):
        assert to_base(500, "g") == (0.5, "kg")

    def test_millilitr_litre_cevrilir(self):
        assert to_base(750, "ml") == (0.75, "l")

    def test_kiloqram_deyismir(self):
        assert to_base(2, "kg") == (2.0, "kg")

    def test_eded_oz_vahidinde_qalir(self):
        assert to_base(10, "pcs") == (10.0, "pcs")

    def test_olcu_yoxdursa_none(self):
        assert to_base(None, "kg") == (None, None)
        assert to_base(1, None) == (None, None)
        assert to_base(1, "qutu") == (None, None)


class TestUnitPrice:
    def test_litr_qiymeti(self):
        # 1.89 AZN / 1.5 L -> 1.26 AZN/L
        assert unit_price(1.89, 1.5, "l") == (1.26, "l")

    def test_qramdan_kiloqram_qiymeti(self):
        # 2.10 AZN / 500 q -> 4.20 AZN/kq
        assert unit_price(2.10, 500, "g") == (4.20, "kg")

    def test_olcu_bilinmirse_none(self):
        # Uydurmuruq - UI-da "—" göstərilir
        assert unit_price(5.0, None, None) == (None, None)

    def test_muqayise_dogru_isleyir(self):
        """1.89/1.5L vs 1.40/1L — insan gözü səhv edir, sistem etməməlidir."""
        a, _ = unit_price(1.89, 1.5, "l")   # 1.26
        b, _ = unit_price(1.40, 1.0, "l")   # 1.40
        assert a < b


class TestSizeToken:
    def test_tam_reqem_sadelesir(self):
        assert size_token(1, "l") == "1l"

    def test_qram_kiloqrama_cevrilir(self):
        assert size_token(500, "g") == "0.5kg"

    def test_olcu_yoxdursa_bos(self):
        assert size_token(None, None) == ""


class TestCanonicalKey:
    def test_soz_sirasi_ehemiyyetsizdir(self):
        a = canonical_key("süd", "Milla", 1, "l")
        b = canonical_key("Milla süd", None, 1, "l")
        assert a == b

    def test_boyuk_kicik_herf_ehemiyyetsizdir(self):
        assert canonical_key("SÜD", "MILLA", 1, "l") == canonical_key("süd", "milla", 1, "l")

    def test_azerbaycan_herfleri_sadelesir(self):
        key = canonical_key("günəbaxan yağı", "Sola", 1.8, "l")
        assert key.isascii(), f"açarda qeyri-ascii simvol qaldı: {key}"

    def test_eyni_olcu_ferqli_vahidde_eyni_acar_verir(self):
        # 1 kq və 1000 q eyni məhsuldur
        assert canonical_key("düyü", None, 1, "kg") == canonical_key("düyü", None, 1000, "g")

    def test_ferqli_olcu_ferqli_acar_verir(self):
        assert canonical_key("süd", "Milla", 1, "l") != canonical_key("süd", "Milla", 2, "l")

    def test_bos_giris_cokmur(self):
        assert canonical_key("", None, None, None) == "namelum"
