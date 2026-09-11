"""
Normalizasiya testləri — deterministik məntiq, LLM yoxdur.

Bu funksiyalar bütün müqayisənin təməlidir: unit_price səhv olsa,
dashboard yanlış marketi "ən ucuz" göstərər və heç kim səbəbini anlamaz.
"""

from ingestion.normalize import (
    brand_from_name,
    canonical_key,
    fat_percent,
    match_key,
    size_from_name,
    size_token,
    to_base,
    unit_price,
)


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

    def test_bravo_acari_deyismir(self):
        """
        canonical_key UNIQUE-dir və mağaza çəkilişi məhsulu onunla tapır.
        Bu açar dəyişsə, növbəti çəkiliş 13 min YENİ sətir yaradar və qiymət
        tarixçəsi ikiyə bölünər. Ölçünü addan oxumaq match_key-in işidir.
        """
        assert canonical_key("Milla Qatıq 1.5% 450qr", None, None, None) == "450qr|milla|qatiq"


# Aşağıdakı adlar BAZADAN götürülüb (Bravo/Wolt kartları, 2026-09-11) —
# uydurma nümunə deyil.


class TestSizeFromName:
    def test_qram_yazilisi(self):
        assert size_from_name("Milla Qatıq 1.5% 450qr") == (450.0, "g")

    def test_kiloqram_kq(self):
        assert size_from_name("Mercan Dondurulmuş Toyuq Pətənəyi 1kq") == (1.0, "kg")

    def test_boyuk_herfli_litr_bosluqla(self):
        assert size_from_name("Sirab Qazsız Su 10 L") == (10.0, "l")

    def test_millilitr(self):
        assert size_from_name("Paradontax Diş Məcunu Ftorsuz 75ml") == (75.0, "ml")

    def test_eded_noqte_ile(self):
        assert size_from_name("Milvana Kənd Yumurtası 10əd.") == (10.0, "pcs")

    def test_eded_moterize_icinde(self):
        assert size_from_name("Tach Qapaqlı Stekan (6əd.)") == (6.0, "pcs")

    def test_vergullu_litr_sozu(self):
        assert size_from_name("Su 1,5 litr") == (1.5, "l")

    def test_faiz_olcu_sayilmir(self):
        assert size_from_name("Milla Süd 2 5% 1l") == (1.0, "l")

    def test_olcu_olcu_yazisi_olcu_deyil(self):
        """«11x8sm» — «8» ölçü deyil, çünki qarşısında hərf var."""
        assert size_from_name("Yumurta Dilimləyici 11x8sm") == (None, None)

    def test_olcu_yoxdursa_none(self):
        assert size_from_name("Azərçay Ətirli Qara Çay") == (None, None)
        assert size_from_name(None) == (None, None)


class TestFatPercent:
    def test_wolt_vergulu_itirir(self):
        assert fat_percent("Milla Süd 2 5% 1l") == 2.5

    def test_noqteli_faiz(self):
        assert fat_percent("Milla Qatıq 1.5% 450qr") == 1.5

    def test_tam_faiz(self):
        assert fat_percent("Savuşkin Tilziter Pendir 45% 200qr") == 45.0

    def test_faiz_yoxdursa_none(self):
        assert fat_percent("Milla süd 1l") is None


class TestBrandFromName:
    BRANDS = {"milla", "ivanovka", "zeytunbaglari", "7days"}

    def test_ilk_soz_brenddir(self):
        assert brand_from_name("Milla Qatıq 1.5% 450qr", self.BRANDS) == "milla"

    def test_brend_ortadadir(self):
        assert brand_from_name("Uzun Ömür İvanovka Qatıq 700qr", self.BRANDS) == "ivanovka"

    def test_ikisozlu_brend(self):
        assert brand_from_name("Zeytun Bağları Zeytun Yağı 1l", self.BRANDS) == "zeytunbaglari"

    def test_reqemli_brend(self):
        assert brand_from_name("7days Kruassan Çiyələk ilə 65qr", self.BRANDS) == "7days"

    def test_taninmayan_brend_none(self):
        assert brand_from_name("Sultan Basmati Düyü 1kq", self.BRANDS) is None


class TestMatchKey:
    def test_bravo_ve_araz_eyni_acar_verir(self):
        """Tapşırığın əsas məqsədi: iki marketin fərqli yazılışı bir açara düşür."""
        bravo = match_key("Milla Süd 2 5% 1l", None, None, None)
        araz = match_key("süd", "Milla", 1.0, "l")
        assert bravo == araz == "milla|sud|1l"

    def test_addaki_olcu_baza_vahidine_cevrilir(self):
        assert match_key("Milla Qatıq 1.5% 450qr", None, None, None) == "milla|qatiq|0.45kg"

    def test_qram_ve_kiloqram_eyni_acar(self):
        bravo = match_key("President Kərə Yağı 82% 200qr", None, None, None)
        araz = match_key("kərə yağı", "President", 200.0, "g")
        assert bravo == araz

    def test_sahedeki_olcu_addakindan_ustundur(self):
        assert match_key("Süd 2l", "Milla", 1.0, "l") == "milla|sud|1l"

    def test_bos_giris_cokmur(self):
        assert match_key("", None, None, None) == "namelum"
