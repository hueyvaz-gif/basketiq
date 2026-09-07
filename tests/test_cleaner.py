"""
Cleaner testləri — LLM olmadan işləyir, ona görə sürətlidir.

Bu testlər layihənin "sığortasıdır": prompt-ları dəyişdikcə pipeline-ın
bu hissəsinin xarab olmadığına əmin olmaq üçün hər dəfə işlədilir.
"""

from ingestion.cleaner import (
    clean_text,
    extract_prices,
    fix_ocr_digits,
    is_noise,
    normalize,
    split_prices,
)


class TestNormalize:
    def test_artiq_bosluqlar_silinir(self):
        assert normalize("  Süd   Milla    1 L  ") == "Süd Milla 1 L"

    def test_ayrilmis_vergul_birlesir(self):
        assert normalize("1 , 89 AZN") == "1,89 AZN"


class TestOcrDigitFix:
    def test_reqemler_arasindaki_herf_duzelir(self):
        assert fix_ocr_digits("1,8O AZN") == "1,80 AZN"
        assert fix_ocr_digits("2,l5") == "2,15"

    def test_adi_soze_toxunmur(self):
        # "Sola" -> "5ola" olmamalıdır
        assert fix_ocr_digits("Sola yağı 1,89") == "Sola yağı 1,89"

    def test_litr_isaresi_qorunur(self):
        # "1,5l" = 1.5 litr. Bunu "1,51" etmək qiyməti korlayardı.
        assert fix_ocr_digits("Su 1,5l 0,60") == "Su 1,5l 0,60"


class TestExtractPrices:
    def test_onluq_qiymet(self):
        assert extract_prices("Süd Milla 1 L 1,89") == [1.89]

    def test_iki_qiymet_sirali_gelir(self):
        assert extract_prices("Yağ Sola 1.8 L 6,20 8,40") == [6.20, 8.40]

    def test_valyuta_ile_tam_qiymet(self):
        assert extract_prices("Düyü 5 AZN") == [5.0]

    def test_valyutasiz_tam_reqem_qiymet_sayilmir(self):
        # "2.5%" və "1 L" qiymət deyil
        assert extract_prices("Süd 2.5% 1 L") == []

    def test_agilsiz_reqem_atilir(self):
        assert extract_prices("Kod 99999,00") == []


class TestIsNoise:
    def test_qiymetsiz_setir_atilir(self):
        assert is_noise("Hörmətli müştərilər", []) is not None

    def test_qisa_setir_atilir(self):
        assert is_noise("AZ", [1.0]) == "cox_qisa"

    def test_reklam_metni_atilir(self):
        reason = is_noise("Endirimlər 12 mart tarixinə qədər etibarlıdır", [12.0])
        assert reason == "reklam_metni"

    def test_normal_mehsul_saxlanilir(self):
        assert is_noise("Süd Milla 2.5% 1 L 1,89", [1.89]) is None


class TestSplitPrices:
    def test_tek_qiymet(self):
        assert split_prices([1.89]) == (1.89, None)

    def test_kohne_ve_cari(self):
        assert split_prices([1.89, 2.45]) == (1.89, 2.45)

    def test_cox_boyuk_ferq_qiymet_sayilmir(self):
        # 1.20 və 500 -> 500 qiymət deyil (yəqin qram və ya kod)
        assert split_prices([1.20, 500.0]) == (1.20, None)


class TestCleanText:
    RAW = """
    BRAVO SUPERMARKET
    Endirimlər 12 mart tarixinə qədər etibarlıdır
    Süd Milla 2.5% 1 L      1,89   2,45
    Düyü Basmati 1 kq       3,40
    ~~~ ### @@@
    Yağ Sola 1.8 L          6,20   8,40
    www.bravo.az
    """

    def test_yalniz_mehsul_setirleri_qalir(self):
        result = clean_text(self.RAW)
        assert result.stats["kept"] == 3
        assert [round(line.price, 2) for line in result.lines] == [1.89, 3.40, 6.20]

    def test_kohne_qiymet_taninir(self):
        result = clean_text(self.RAW)
        assert result.lines[0].old_price == 2.45
        assert result.lines[1].old_price is None

    def test_xam_setir_saxlanilir(self):
        # Şəffaflıq: AI-nin nədən çıxardığını həmişə göstərə bilməliyik
        result = clean_text(self.RAW)
        assert "Süd Milla" in result.lines[0].raw

    def test_statistika_doludur(self):
        stats = clean_text(self.RAW).stats
        assert stats["total_lines"] > stats["kept"]
        assert 0 < stats["keep_ratio"] < 1
        assert sum(stats["dropped"].values()) == stats["total_lines"] - stats["kept"]

    def test_bos_metn_cokmur(self):
        result = clean_text("")
        assert result.lines == []
        assert result.stats["keep_ratio"] == 0.0
