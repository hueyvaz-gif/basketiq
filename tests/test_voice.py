"""
Səs əmri testləri.

ÜÇ QAT AYRI YOXLANILIR, çünki üçü ayrı səbəbdən qırılır:

  1. commands.py  - mətni düzgün başa düşürmü?   (şəbəkə/model lazım deyil)
  2. actions.py   - əmri düzgün icra edirmi?     (baza lazımdır)
  3. bot.py       - Telegram ilə düzgün danışırmı? (HTTP mock edilir)

Whisper-in ÖZÜ burada sınanmır: model 460 MB-dır və hər çağırış 10+ saniyə
çəkir. Onun yerinə transkripsiya mock edilir - biz zəncirin qoşulmasını
yoxlayırıq, Whisper-in dəqiqliyini yox (o, OpenAI-nin işidir).
Real səs sınağı üçün: `python tools/voice_check.py <fayl.wav>`
"""

import pytest
from fastapi.testclient import TestClient

from app.db import db_cursor, get_connection
from app.main import app
from voice import bot as bot_module
from voice.actions import run
from voice.commands import Command, extract_qty, extract_query, parse_regex


# ------------------------------------------------------------------ niyyət


@pytest.mark.parametrize("text,intent", [
    ("səbətə iki litr süd əlavə et", "add"),
    ("səbətimə bir kilo düyü at", "add"),
    ("səbətdən südü çıxar", "remove"),
    ("süd sil", "remove"),
    ("səbətimdə nə var", "show"),
    ("səbətim harada ucuzdur", "compare"),
    ("hansı marketdə ucuzdur", "compare"),
    ("müqayisə et", "compare"),
    ("düyü neçəyədir", "price"),
    ("günəbaxan yağı qiyməti", "price"),
    ("makaron axtar", "price"),
    ("hava necədir", "unknown"),
    ("", "unknown"),
])
def test_niyyet_taninir(text, intent):
    assert parse_regex(text).intent == intent


def test_muqayise_gosterden_ustundur():
    """
    "səbətim harada ucuzdur" cümləsində hər iki açar söz var.

    Sıra pozulsa, istifadəçi müqayisə istəyəndə səbətin siyahısını alar -
    bu, səssiz və qıcıqlandırıcı səhvdir.
    """
    assert parse_regex("səbətim harada ucuzdur").intent == "compare"
    assert parse_regex("səbətimdə nə var").intent == "show"


# ------------------------------------------------------------------ miqdar


@pytest.mark.parametrize("text,qty", [
    ("iki litr süd", 2),
    ("bir kilo düyü", 1),
    ("üç ədəd yumurta", 3),
    ("1.5 litr su", 1.5),
    ("yarım kilo şəkər", 0.5),
    ("on paket makaron", 10),
])
def test_miqdar_cixarilir(text, qty):
    assert extract_qty(text) == qty


def test_olcu_sozu_yoxdursa_miqdar_birdir():
    """
    "coca cola 2" ifadəsindəki rəqəm miqdar deyil, adın hissəsidir.

    Səhv miqdar səbətə SƏSSİZCƏ düşür - istifadəçi 2 əvəzinə 5 litr süd
    sifariş etdiyini yalnız mağazada görər. Ona görə şübhəli halda 1 götürülür.
    """
    assert extract_qty("coca cola 2") == 1.0
    assert extract_qty("süd əlavə et") == 1.0


def test_mehsul_adi_emr_sozlerinden_temizlenir():
    assert extract_query("səbətə iki litr süd əlavə et") == "süd"
    assert extract_query("zəhmət olmasa üç ədəd yumurta əlavə et") == "yumurta"
    # Feillər də atılır - əks halda axtarış "düyü satılır" ilə heç nə tapmır
    assert extract_query("düyü neçəyə satılır") == "düyü"


def test_mehsul_adi_yoxdursa_emr_qebul_edilmir():
    """"səbətə əlavə et" - nəyi? Bu, icra edilməməli, soruşulmalıdır."""
    command = parse_regex("səbətə əlavə et")
    assert command.intent == "unknown"
    assert "adı" in command.note


# ------------------------------------------------------------------ icra


@pytest.fixture
def sebet_qorunur():
    conn = get_connection()
    before = [
        dict(r) for r in conn.execute(
            "SELECT product_id, qty FROM basket_items WHERE basket_id = 1"
        ).fetchall()
    ]
    product = conn.execute(
        "SELECT id, name FROM products WHERE name LIKE '%süd%' LIMIT 1"
    ).fetchone() or conn.execute("SELECT id, name FROM products LIMIT 1").fetchone()
    conn.close()
    if product is None:
        pytest.skip("Bazada məhsul yoxdur")

    yield dict(product)

    with db_cursor() as cur:
        cur.execute("DELETE FROM basket_items WHERE basket_id = 1")
        for row in before:
            cur.execute(
                "INSERT INTO basket_items (basket_id, product_id, qty) VALUES (1, ?, ?)",
                (row["product_id"], row["qty"]),
            )


def test_taninmayan_emr_numune_gosterir():
    """"Başa düşmədim" tək başına faydasızdır - nə deyə biləcəyini göstər."""
    reply = run(Command(intent="unknown", raw="hava necədir"))
    assert "səbətə" in reply.lower()
    assert reply.count("•") >= 3


def test_sebete_elave_ve_cixarma(sebet_qorunur):
    name = sebet_qorunur["name"]
    reply = run(Command(intent="add", query=name, qty=2))
    assert "əlavə olundu" in reply

    reply = run(Command(intent="show"))
    assert name.lower() in reply.lower()

    reply = run(Command(intent="remove", query=name))
    assert "çıxarıldı" in reply


def test_tapilmayan_mehsul_aydin_cavab(sebet_qorunur):
    reply = run(Command(intent="add", query="beləməhsulyoxdur", qty=1))
    assert "tapılmadı" in reply


def test_axtarisda_geri_cekilme(sebet_qorunur):
    """
    Səs mətnində əmr sözü qala bilər. Tam sorğu heç nə tapmasa, sözlər
    bir-bir yoxlanılır. Diqqət: zibil söz məhsulun adından UZUN ola bilər
    ("tapilmayansoz" 13 hərf, "düyü" 4) - ona görə uzunluq yalnız sıranı
    müəyyən edir, seçimi yox.
    """
    reply = run(Command(intent="price", query="düyü tapilmayansoz"))
    assert "tapılmadı" not in reply


# ------------------------------------------------------------------ Telegram


class FakeTelegram:
    """Telegram API-ni əvəz edir - şəbəkəyə çıxmadan botun məntiqini yoxlayır."""

    def __init__(self):
        self.sent: list[tuple[int, str]] = []
        self.files: dict[str, bytes] = {}

    def call(self, method: str, **params):
        if method == "sendMessage":
            self.sent.append((params["chat_id"], params["text"]))
            return {"message_id": len(self.sent)}
        if method == "getFile":
            return {"file_path": "voice/x.ogg", "file_size": 1024}
        raise AssertionError(f"gözlənilməyən metod: {method}")


@pytest.fixture
def fake_telegram(monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr(bot_module, "_call", fake.call)
    monkeypatch.setattr(bot_module.settings, "telegram_bot_token", "test-token")
    return fake


def test_start_emri_komek_gosterir(fake_telegram):
    bot_module.handle({"message": {"chat": {"id": 5}, "text": "/start"}})
    assert len(fake_telegram.sent) == 1
    assert "BasketIQ" in fake_telegram.sent[0][1]


def test_metn_mesaji_emr_kimi_islenir(fake_telegram, monkeypatch):
    monkeypatch.setattr(bot_module.settings, "voice_llm_fallback", False)
    bot_module.handle({"message": {"chat": {"id": 5}, "text": "səbətimdə nə var"}})
    assert any("Səbət" in text for _, text in fake_telegram.sent)


def test_ses_mesajinda_transkript_gosterilir(fake_telegram, monkeypatch):
    """
    Eşidilən mətn HƏMİŞƏ göstərilir.

    Whisper səhv oxuyanda istifadəçi səbəbi dərhal görür. Bu olmasa, bot
    "başa düşmədim" deyəcək və istifadəçi niyəsini bilməyəcək.
    """
    from voice.transcribe import Transcript

    monkeypatch.setattr(bot_module.settings, "voice_llm_fallback", False)
    monkeypatch.setattr(bot_module, "download_voice", lambda file_id: b"fake-audio")
    monkeypatch.setattr(
        "voice.transcribe.transcribe",
        lambda audio, language="az": Transcript(text="səbətimdə nə var"),
    )

    bot_module.handle({
        "message": {"chat": {"id": 7}, "voice": {"file_id": "abc", "duration": 3}}
    })

    texts = [text for _, text in fake_telegram.sent]
    assert texts[0] == "Səsi dinləyirəm…"
    assert any("Eşitdim" in t for t in texts)


def test_transkripsiya_xetasi_istifadeciye_catir(fake_telegram, monkeypatch):
    def broken(file_id):
        raise RuntimeError("model yüklənmədi")

    monkeypatch.setattr(bot_module, "download_voice", broken)
    bot_module.handle({
        "message": {"chat": {"id": 7}, "voice": {"file_id": "abc", "duration": 3}}
    })
    assert any("tanıya bilmədim" in text for _, text in fake_telegram.sent)


def test_desteklenmeyen_mesaj_tipi(fake_telegram):
    bot_module.handle({"message": {"chat": {"id": 9}, "photo": [{"file_id": "x"}]}})
    assert any("mətn və səs" in text for _, text in fake_telegram.sent)


# ------------------------------------------------------------------ API


def test_metn_endpointi():
    with TestClient(app) as client:
        res = client.post(
            "/api/voice/text",
            data={"text": "səbətim harada ucuzdur", "use_llm": "false"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["command"]["intent"] == "compare"
        assert data["reply"]


def test_bos_audio_reddedilir():
    with TestClient(app) as client:
        res = client.post("/api/voice", files={"file": ("x.ogg", b"", "audio/ogg")})
        assert res.status_code == 400


def test_ses_modulu_yoxdursa_nə_etmək_lazım_olduğu_deyilir(monkeypatch):
    """
    "ModuleNotFoundError" cavabı istifadəçiyə heç nə demir.

    Səs bonusu ayrıca quraşdırılır (image 684 MB -> 1.25 GB), ona görə bu hal
    normaldır və cavab konkret əmri göstərməlidir.
    """
    def missing(audio, language="az"):
        raise ModuleNotFoundError("No module named 'faster_whisper'")

    monkeypatch.setattr("voice.transcribe.transcribe", missing)
    with TestClient(app) as client:
        res = client.post(
            "/api/voice", files={"file": ("x.ogg", b"fake-audio", "audio/ogg")}
        )
        assert res.status_code == 503
        assert "requirements-voice.txt" in res.json()["detail"]


def test_transkripsiya_qirilanda_503(monkeypatch):
    """Whisper quraşdırılmayıbsa bu, 500 deyil - konfiqurasiya məsələsidir."""
    def broken(audio, language="az"):
        raise RuntimeError("faster-whisper quraşdırılmayıb")

    monkeypatch.setattr("voice.transcribe.transcribe", broken)
    with TestClient(app) as client:
        res = client.post(
            "/api/voice", files={"file": ("x.ogg", b"fake-audio", "audio/ogg")}
        )
        assert res.status_code == 503
        assert "Səs tanınmadı" in res.json()["detail"]
