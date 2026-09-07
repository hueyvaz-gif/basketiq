"""
Claude (əsas) + Ollama (ehtiyat) seçimi və fallback davranışı.

BURADA NƏ SINANIR, NƏ SINANMIR:
Claude API-ya real sorğu GÖNDƏRİLMİR - o, pul və açar tələb edir, üstəlik
test şəbəkədən asılı olmamalıdır. Sınanan şey BİZİM məntiqimizdir:

  - açar yoxdursa Claude ümumiyyətlə qurulmur (boş yerə 401 gözləmirik)
  - provider "claude" olanda zəncir fallback-li olur
  - əsas model qırılanda sorğu HƏQİQƏTƏN ehtiyata keçir
  - keş açarı aktiv modelin adını daşıyır

Fallback saxta modellə yoxlanılır: birincisi həmişə xəta atır, ikincisi
cavab verir. Bu, Claude-un qırılmasının dəqiq ekvivalentidir.
"""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

from ai import llm as llm_module
from ai.llm import active_model_name, check_llm, claude_enabled, get_llm


@pytest.fixture
def claude_provider(monkeypatch):
    """Provider "claude", açar var - amma şəbəkəyə çıxmırıq."""
    monkeypatch.setattr(llm_module.settings, "llm_provider", "claude")
    monkeypatch.setattr(llm_module.settings, "anthropic_api_key", "test-key-deyil-real")


@pytest.fixture
def ollama_provider(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "llm_provider", "ollama")


# ------------------------------------------------------------------ seçim


def test_defolt_provider_ollamadir(ollama_provider):
    assert claude_enabled() is False
    assert active_model_name() == llm_module.settings.ollama_model


def test_acar_yoxdursa_claude_isə_düşmür(monkeypatch):
    """
    Açarsız ChatAnthropic yaratmaq mənasızdır: hər sorğu 401 alıb fallback-ə
    düşərdi - nəticə düzgün olardı, amma hər çağırışa boş şəbəkə gecikməsi
    əlavə edərdi.
    """
    monkeypatch.setattr(llm_module.settings, "llm_provider", "claude")
    monkeypatch.setattr(llm_module.settings, "anthropic_api_key", "")
    assert claude_enabled() is False
    assert active_model_name() == llm_module.settings.ollama_model


def test_claude_secilende_aktiv_model_adi_deyisir(claude_provider):
    assert claude_enabled() is True
    assert active_model_name() == llm_module.settings.llm_claude_model


def test_kes_aciari_modelə_baglidir(claude_provider, monkeypatch):
    """
    Keş açarı model adını daşımalıdır - əks halda Claude-un cavabı Ollama-nın
    keşindən oxunar (və əksinə), yəni nəticə səhv modeldən gələr.
    """
    from ai import cache

    claude_key = cache.cache_key(active_model_name(), "v1", "süd 1 l 1.89")
    monkeypatch.setattr(llm_module.settings, "llm_provider", "ollama")
    ollama_key = cache.cache_key(active_model_name(), "v1", "süd 1 l 1.89")
    assert claude_key != ollama_key


# ------------------------------------------------------------------ fallback


def test_zencir_fallbackli_qurulur(claude_provider, monkeypatch):
    """provider=claude olanda get_llm() ehtiyatı olan obyekt qaytarmalıdır."""
    monkeypatch.setattr(
        llm_module, "build_claude", lambda t, n: FakeListChatModel(responses=["ok"])
    )
    chain = get_llm()
    assert hasattr(chain, "fallbacks"), "fallback zənciri qurulmadı"
    assert len(chain.fallbacks) == 1


def test_esas_model_qirilanda_ehtiyat_isə_düşür(claude_provider, monkeypatch):
    """
    ƏSAS TEST: Claude qırılanda sorğu sükutla Ollama-ya keçməlidir.

    Saxta "Claude" həmişə xəta atır, saxta "Ollama" isə cavab verir.
    Nəticə ehtiyatdan gəlməlidir - yəni istifadəçi xəta görməməlidir.
    """
    def qirilan(_input):
        raise RuntimeError("Claude əlçatmazdır (limit/şəbəkə/açar)")

    ehtiyat = FakeListChatModel(responses=["ehtiyatdan gələn cavab"])
    monkeypatch.setattr(llm_module, "build_claude",
                        lambda t, n: RunnableLambda(qirilan))
    monkeypatch.setattr(llm_module, "build_ollama",
                        lambda t, n, json_mode=False: ehtiyat)

    result = get_llm().invoke("səbətim harada ucuzdur")
    assert "ehtiyatdan" in result.content


def test_esas_model_islyeirse_ehtiyat_cagirilmir(claude_provider, monkeypatch):
    cagirildi = {"ehtiyat": False}

    def ehtiyat_func(_input):
        cagirildi["ehtiyat"] = True
        return "ehtiyat"

    monkeypatch.setattr(llm_module, "build_claude",
                        lambda t, n: FakeListChatModel(responses=["əsasdan cavab"]))
    monkeypatch.setattr(llm_module, "build_ollama",
                        lambda t, n, json_mode=False: RunnableLambda(ehtiyat_func))

    result = get_llm().invoke("salam")
    assert "əsasdan" in result.content
    assert cagirildi["ehtiyat"] is False, "əsas model işləyirkən ehtiyat çağırıldı"


def test_claude_qurulmasa_layihe_dayanmir(claude_provider, monkeypatch):
    """Paket yoxdursa və ya konfiqurasiya səhvdirsə, Ollama ilə davam edilir."""
    def partlayan(t, n):
        raise ImportError("langchain_anthropic quraşdırılmayıb")

    monkeypatch.setattr(llm_module, "build_claude", partlayan)
    chain = get_llm()
    assert not hasattr(chain, "fallbacks"), "fallback yox, birbaşa Ollama gözlənilirdi"


# ------------------------------------------------- model parametrləri (regressiya)
#
# Aşağıdakı iki test SƏNƏDDƏN yox, REAL SƏHVDƏN doğulub. İkisi də eyni
# xüsusiyyətə malikdir: fallback onları GİZLƏDİRDİ. Claude qırılırdı, sorğu
# sükutla Ollama-ya düşürdü, /health "claude" yazırdı - amma Claude bir dəfə də
# işləmirdi. Ona görə bu iki şeyi ayrıca kilidləyirik.


def test_yeni_modele_temperature_gonderilmir(claude_provider, monkeypatch):
    """
    Opus 5 / Sonnet 5 kimi modellərdə `temperature` ÇIXARILIB:
        400 invalid_request_error: `temperature` is deprecated for this model.
    """
    tutulan = {}

    class SaxtaChatAnthropic:
        def __init__(self, **kwargs):
            tutulan.update(kwargs)

    import langchain_anthropic
    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", SaxtaChatAnthropic)
    monkeypatch.setattr(llm_module.settings, "llm_claude_model", "claude-opus-5")

    llm_module.build_claude(0.0, 4000)
    assert "temperature" not in tutulan
    assert tutulan["max_tokens"] == 4000
    assert tutulan["output_config"] == {"effort": llm_module.settings.llm_claude_effort}


def test_kohne_model_temperature_saxlayir(claude_provider, monkeypatch):
    """Haiku hələ də temperature qəbul edir - determinizmi itirməyək."""
    tutulan = {}

    class SaxtaChatAnthropic:
        def __init__(self, **kwargs):
            tutulan.update(kwargs)

    import langchain_anthropic
    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", SaxtaChatAnthropic)
    monkeypatch.setattr(llm_module.settings, "llm_claude_model", "claude-haiku-4-5")

    llm_module.build_claude(0.0, 4000)
    assert tutulan["temperature"] == 0.0


def test_claude_blok_siyahisindan_metn_cixarilir():
    """
    Claude cavabı blok siyahısıdır (düşünmə + mətn), Ollama-nınkı sadə sətir.
    Zəncirin ortasındakı `json.loads()` yalnız sətir qəbul edir - siyahı gəlsə
    TypeError atır və `.with_retry()` səbəbindən sətir sükutla ATILIR.
    """
    from langchain_core.messages import AIMessage

    claude_cavabi = AIMessage(content=[
        {"type": "thinking", "thinking": "", "signature": "xxx"},
        {"type": "text", "text": '{"n":"süd"}'},
    ])
    ollama_cavabi = AIMessage(content='{"n":"süd"}')

    assert llm_module.message_text(claude_cavabi) == '{"n":"süd"}'
    assert llm_module.message_text(ollama_cavabi) == '{"n":"süd"}'


def test_zencir_claude_cavabini_parse_edir():
    """Uçdan-uca: blok siyahısı -> açılmış JSON (şəbəkə YOXDUR)."""
    import json

    from langchain_core.messages import AIMessage

    from ai.chains import expand_short_keys

    cavab = AIMessage(content=[
        {"type": "thinking", "thinking": "", "signature": "xxx"},
        {"type": "text", "text": '{"n":"süd","b":"Milla","v":1,"u":"l","c":1}'},
    ])
    data = json.loads(expand_short_keys(cavab))
    assert data["name"] == "süd"
    assert data["size_unit"] == "l"


# ------------------------------------------------------------------ health


def test_health_provideri_gosterir(claude_provider):
    info = check_llm()
    assert info["provider"] == "claude"
    assert info["claude_model"] == llm_module.settings.llm_claude_model
    assert info["claude_active"] is True


def test_health_acar_yoxdursa_izah_edir(monkeypatch):
    monkeypatch.setattr(llm_module.settings, "llm_provider", "claude")
    monkeypatch.setattr(llm_module.settings, "anthropic_api_key", "")
    info = check_llm()
    assert info["claude_active"] is False
    assert "ANTHROPIC_API_KEY" in info["claude_note"]


def test_health_ollama_rejiminde_claude_sahesi_yoxdur(ollama_provider):
    info = check_llm()
    assert info["provider"] == "ollama"
    assert "claude_model" not in info
