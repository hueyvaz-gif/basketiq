"""
Məhsul şəkilləri qatının sınaqları (M3).

BU FAYL ŞƏBƏKƏYƏ ÇIXMIR. Bütün sınaqlar ya təmiz funksiyaları yoxlayır
(uyğunlaşdırma, ölçü, brend), ya da `fetch`-i əvəzləyir. Səbəb sadədir:
şəbəkədən asılı test bir gün Araz saytı dəyişəndə sınır və o sınıq
BİZİM kodumuzla bağlı olmur - belə test qapını qorumaqdan çıxıb ona
mane olur.
"""

import pytest

from app.services import product_images as pi


# ------------------------------------------------------------------ ölçü


@pytest.mark.parametrize(
    "mətn, gözlənilən",
    [
        ("borjomi-mineral-su-750ml", ("ml", 750.0)),
        ("zateya-gunebaxan-yagi-1-l", ("ml", 1000.0)),
        ("richmond-seker-tozu-800qr", ("g", 800.0)),
        ("pegah-kere-yagi-82-1kq", ("g", 1000.0)),
        ("flomaster", None),
    ],
)
def test_ölçü_oxunur(mətn, gözlənilən):
    assert pi.parse_size(mətn) == gözlənilən


def test_ölçü_ziddiyyəti_yalnız_hər_ikisi_məlum_olanda():
    # Biri bilinmirsə bu, ziddiyyət DEYİL - məlumatın yoxluğudur.
    assert pi.size_conflict(("ml", 500.0), None) is False
    assert pi.size_conflict(None, ("ml", 500.0)) is False
    # Fərqli vahid növü müqayisə edilmir: eyni məhsul iki cür ölçülə bilər.
    assert pi.size_conflict(("g", 500.0), ("ml", 500.0)) is False
    # Yuvarlaqlaşdırma fərq deyil: 500 q = 0.5 kq.
    assert pi.size_conflict(("g", 500.0), ("g", 500.0)) is False
    assert pi.size_conflict(("ml", 750.0), ("ml", 500.0)) is True


# ------------------------------------------------------ tokenlər və bal


def test_slug_vahidləri_və_id_atır():
    tokenlər = pi.slug_tokens("https://x/az/products/milla-sud-32-1l-7759")
    assert "milla" in tokenlər and "sud" in tokenlər
    assert "l" not in tokenlər          # vahid ad deyil
    assert "7759" not in tokenlər       # saytın daxili id-si


def test_çatışmayan_söz_artıq_sözdən_AĞIR_cəzalanır():
    """
    M3-ün əsas dərsi: «Palmolive MAYE sabun» → bərk sabun səhvi buradan
    çıxmışdı. Simmetrik ölçü (harmonik orta) iki halı eyni saydığı üçün
    hər ikisi 0.75 alırdı.
    """
    bizim = ["palmolive", "maye", "sabun"]
    çatışmayan = pi.match_score(bizim, ["palmolive", "sabun", "zeytun"], "Palmolive")
    artıq = pi.match_score(["elidor", "sampun"], ["elidor", "sampun", "keratin"], "Elidor")
    assert çatışmayan < 0.75 <= artıq


def test_tam_uyğunluq_bir_verir():
    assert pi.match_score(["heineken", "pive"], ["heineken", "pive"], "Heineken") == 1.0


def test_ortaq_söz_yoxdursa_sıfır():
    assert pi.match_score(["flomaster"], ["bonduelle", "qargidali"], None) == 0.0


# ------------------------------------------------------------- sərt qaydalar


def test_ölçü_ziddiyyəti_namizədi_baldan_asılı_olmayaraq_atır():
    namizədlər = [
        pi.Candidate(url="https://x/az/products/heineken-pive-500ml", tokens=["heineken", "pive"],
                     size=("ml", 500.0)),
    ]
    n = pi.pick_best("pivə", "Heineken", ("ml", 330.0), namizədlər)
    assert n.candidate is None
    assert "namizəd yoxdur" in n.reason


def test_variant_bərabərliyi_rədd_deyil():
    """
    Bərabər namizədlərin hamısı bizim BÜTÜN sözlərimizi ehtiva edirsə, onlar
    eyni məhsulun variantlarıdır (1 l / 1.8 lt / 500 ml) - hansını seçsək,
    bildiyimiz hər şeyə uyğundur. Seçim TƏYİNATLIDIR: ən qısa slug.
    """
    namizədlər = [
        pi.Candidate(url="https://x/az/products/zateya-gunebaxan-yagi-18-lt",
                     tokens=["zateya", "gunebaxan", "yagi", "18", "lt"]),
        pi.Candidate(url="https://x/az/products/zateya-gunebaxan-yagi-1-l",
                     tokens=["zateya", "gunebaxan", "yagi"]),
    ]
    n = pi.pick_best("günəbaxan yağı", "Zateya", None, namizədlər)
    assert n.candidate is not None
    assert n.candidate.url.endswith("zateya-gunebaxan-yagi-1-l")
    # İki dəfə çağırış eyni nəticə verməlidir - şəkil hər gün dəyişməməlidir.
    yenidən = pi.pick_best("günəbaxan yağı", "Zateya", None, namizədlər)
    assert yenidən.candidate.url == n.candidate.url


def test_fərqli_məhsul_bərabərliyi_RƏDD_edilir():
    """
    Bərabər namizədlər bizim bir sözümüzü ÖRTMÜRSƏ, onlar variant deyil -
    başqa məhsul ola bilər. Burada «qaymaqlı» heç birində yoxdur: hansını
    seçsək, bilmədiyimiz bir şeyi uydurmuş olarıq.
    """
    namizədlər = [
        pi.Candidate(url="https://x/az/products/tac-pecenye-kakaolu",
                     tokens=["tac", "pecenye"]),
        pi.Candidate(url="https://x/az/products/tac-pecenye-vanilli",
                     tokens=["tac", "pecenye"]),
    ]
    n = pi.pick_best("peçenye qaymaqlı", "Tac", None, namizədlər)
    assert n.candidate is None
    assert "bərabər" in n.reason


def test_zəif_uyğunluq_eşiyi_keçmir():
    """«Tac peçenye» ↔ «tac-narşərab»: yalnız brend ortaqdır."""
    namizədlər = [
        pi.Candidate(url="https://x/az/products/tac-narserab-250-qr", tokens=["tac", "narserab"]),
    ]
    n = pi.pick_best("peçenye", "Tac", None, namizədlər)
    assert n.candidate is None
    assert "etibar aşağıdır" in n.reason


def test_adı_olmayan_məhsul_rədd_edilir():
    assert pi.pick_best(None, None, None, []).candidate is None


# ------------------------------------------------------------ təkrar cəhd


def test_manual_sətir_avtomatikaya_bağlıdır():
    """`manual` sətir NƏ vaxtı çatanda, NƏ də uğursuzluqdan sonra yenidən çəkilmir."""
    assert pi.needs_fetch({"status": "ok", "manual": 1, "fetched_at": "2000-01-01"}) is False
    assert pi.needs_fetch({"status": "rejected", "manual": 1, "fetched_at": "2000-01-01"}) is False


def test_rədd_edilən_avtomatik_təkrarlanmır():
    """
    Rədd qərarı ÖLÇÜLMÜŞ səbəbə görə verilib (bal aşağıdır, brend yaddır).
    Sabah eyni data ilə eyni nəticə çıxacaq - hər gün yenidən sınamaq
    sayta boş sorğu göndərmək olardı.
    """
    assert pi.needs_fetch({"status": "rejected", "manual": 0, "fetched_at": "2000-01-01"}) is False


def test_uğursuz_həftədə_bir_təkrarlanır():
    from datetime import date, timedelta
    bugün = date(2026, 9, 10)
    indi = bugün.isoformat()
    təzə = (bugün - timedelta(days=2)).isoformat()
    köhnə = (bugün - timedelta(days=pi.RETRY_FAILED_DAYS + 1)).isoformat()
    assert pi.needs_fetch({"status": "failed", "manual": 0, "fetched_at": təzə}, indi) is False
    assert pi.needs_fetch({"status": "failed", "manual": 0, "fetched_at": köhnə}, indi) is True


def test_şəkli_olan_ayda_bir_yoxlanılır():
    from datetime import date, timedelta
    bugün = date(2026, 9, 10)
    indi = bugün.isoformat()
    təzə = (bugün - timedelta(days=5)).isoformat()
    köhnə = (bugün - timedelta(days=pi.RECHECK_OK_DAYS + 1)).isoformat()
    assert pi.needs_fetch({"status": "ok", "manual": 0, "fetched_at": təzə}, indi) is False
    assert pi.needs_fetch({"status": "ok", "manual": 0, "fetched_at": köhnə}, indi) is True


def test_şəkli_olmayan_məhsul_həmişə_çəkilir():
    assert pi.needs_fetch(None) is True


# --------------------------------------------------------- HTML çıxarışı


def test_og_image_oxunur():
    html = '<html><head><meta property="og:image" content="https://x/foto.png"></head></html>'
    assert pi.extract_image_url(html) == "https://x/foto.png"


def test_şəkilsiz_səhifə_none_qaytarır():
    assert pi.extract_image_url("<html><head></head></html>") is None


# ------------------------------------------------- endirmə: sərt yoxlamalar


class _FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def test_şəkil_olmayan_content_type_rədd_edilir(monkeypatch):
    """Kənardan gələn fayla inanmırıq: `text/html` gəlsə, o, şəkil deyil."""
    monkeypatch.setattr(pi, "fetch",
                        lambda *a, **k: (_FakeHeaders({"Content-Type": "text/html"}), b"<html>"))
    assert pi.download_image("https://x/foto.png") is None


def test_hədddən_böyük_fayl_rədd_edilir(monkeypatch):
    böyük = b"x" * (pi.settings.product_image_max_bytes + 1)
    monkeypatch.setattr(pi, "fetch",
                        lambda *a, **k: (_FakeHeaders({"Content-Type": "image/png"}), böyük))
    assert pi.download_image("https://x/foto.png") is None


def test_zədəli_şəkil_prosesi_dayandırmır(monkeypatch):
    """PIL açmasa, `None` qayıdır - istisna atılmır, çünki qalan məhsullar gözləyir."""
    monkeypatch.setattr(pi, "fetch",
                        lambda *a, **k: (_FakeHeaders({"Content-Type": "image/png"}), b"not-an-image"))
    assert pi.download_image("https://x/zedeli.png") is None


def test_sayt_cavab_vermirsə_çəkiliş_sakitcə_dayanır(monkeypatch):
    """
    QAPI ŞƏRTİ: şəkil xidməti tamamilə sönsə də, proses istisna atmır -
    sadəcə hesabatda səbəb yazılır. Sayt bundan xəbər tutmamalıdır.
    """
    monkeypatch.setattr(pi, "fetch", lambda *a, **k: None)
    hesabat = pi.assign_images(limit=1)
    assert "xəta" in hesabat
    assert hesabat["ok"] == 0


def test_robots_oxunmursa_icazə_verilmiş_sayılmır(monkeypatch):
    """Şübhə saytın xeyrinə həll olunur: robots.txt gəlmirsə, çəkmirik."""
    monkeypatch.setattr(pi, "fetch", lambda *a, **k: None)
    assert pi.robots_allows("https://www.arazmarket.az/az/products/x") is False


# ------------------------------------------------- kvadrat kətan (normallaşma)


def _webp(en: int, hünd: int, rəng=(30, 90, 200)) -> bytes:
    """Verilmiş ölçüdə, ortasında rəngli düzbucaqlı olan test şəkli."""
    import io as _io

    from PIL import Image

    im = Image.new("RGB", (en, hünd), (255, 255, 255))
    im.paste(Image.new("RGB", (en // 2, hünd // 2), rəng), (en // 4, hünd // 4))
    buf = _io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_enli_şəkil_kvadrat_kətana_oturur():
    """
    ÖLÇÜLDÜ: mənbədən gələn 32 fotodan 31-i enli idi (600×337), plitə isə
    1:1-dir - `contain` ilə hündürlüyün ~44%-i boş qalırdı və şəkilli
    kartlar bir-birindən fərqli «ağırlıqda» oxunurdu.
    """
    nəticə = pi._image_bytes_to_webp(_webp(600, 337))
    assert nəticə is not None
    _, en, hünd = nəticə
    assert en == hünd == pi.settings.product_image_max_side


def test_hündür_şəkil_də_eyni_kətana_oturur():
    nəticə = pi._image_bytes_to_webp(_webp(300, 900))
    assert nəticə is not None
    _, en, hünd = nəticə
    assert en == hünd == pi.settings.product_image_max_side


def test_kənardakı_boşluq_kəsilir():
    """
    Kəsmədən «eyni kətan» yalnız FORMANI düzəldər, ÖLÇÜ fərqi qalar: geniş
    boşluqlu şəkil kətanda kiçik, sıx şəkil isə böyük görünərdi.
    """
    from PIL import Image

    im = Image.new("RGB", (400, 400), (255, 255, 255))
    im.paste(Image.new("RGB", (40, 40), (10, 10, 10)), (180, 180))
    assert pi._content_box(im) == (180, 180, 220, 220)


def test_boş_şəkil_kəsilmir():
    """Tamamilə ağ kadr: kəsiləcək məzmun yoxdur - bütöv qaytarılır, sınmır."""
    from PIL import Image

    ağ = Image.new("RGB", (200, 100), (255, 255, 255))
    assert pi._content_box(ağ) == (0, 0, 200, 100)


def test_kiçik_şəkil_süni_böyüdülmür():
    """200px fotonu 516px-ə dartmaq onu bulanıqlaşdırar - kətanda kiçik qalır."""
    from PIL import Image

    kiçik = Image.new("RGB", (60, 60), (0, 0, 0))
    kətan = pi._to_square(kiçik)
    assert kətan.size == (pi.settings.product_image_max_side,) * 2
    # Qara kvadrat 60px qalmalıdır: kətanın ortasında say.
    orta = kətan.height // 2
    qara = sum(1 for x in range(kətan.width) if kətan.getpixel((x, orta)) == (0, 0, 0))
    assert qara <= 62, f"şəkil böyüdülüb: {qara}px"
