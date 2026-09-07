"""
LLM-ə tək giriş nöqtəsi: Claude API (əsas) + Ollama (ehtiyat).

NİYƏ İKİ MODEL?
Ollama lokal və pulsuzdur, amma bu maşında GPU olmadığı üçün yavaşdır
(ölçülüb: cavab yazması 4.5 token/saniyə). Claude API sürətlidir, amma
internet, açar və pul tələb edir. İkisini birləşdiririk:

    LLM_PROVIDER=claude  ->  Claude əsas, Ollama EHTİYAT
    LLM_PROVIDER=ollama  ->  yalnız Ollama (defolt)

Claude qırılanda (açar bitib, limit aşılıb, internet yoxdur) sorğu SÜKUTLA
Ollama-ya keçir. Yəni layihə internetsiz də işləməyə davam edir - sadəcə
yavaş. Bu, deployment üçün vacibdir: LLM xidmətinin dayanması bütün
dashboard-u dayandırmamalıdır.

NECƏ İŞLƏYİR?
LangChain-in öz mexanizmi: `runnable.with_fallbacks([ehtiyat])`. Zəncirlərdə
(`ai/chains.py`, `ai/advisor.py`, `ai/matcher.py`) HEÇ NƏ dəyişmir - onlar
`get_llm()`-dən gələn obyekti `prompt | llm | parser` kimi işlədirlər və
`.batch()`, `.astream()` metodları eyni qalır.

NİYƏ `langchain_anthropic`, birbaşa `anthropic` SDK deyil?
Layihənin bütün AI qatı LCEL zəncirlərindən ibarətdir. Birbaşa SDK işlətsək,
zəncirləri sökmək və fallback-i əl ilə yazmaq lazım gələrdi.
`langchain_anthropic.ChatAnthropic` içəridə elə rəsmi `anthropic` SDK-nı
çağırır - yəni SDK-dan imtina etmirik, onu LCEL interfeysi ilə işlədirik.
"""

import requests
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama

from app.config import settings


def build_ollama(
    temperature: float, num_predict: int, json_mode: bool = False
) -> ChatOllama:
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=temperature,
        # format="json" -> Ollama modeli SİNTAKTİK olaraq düzgün JSON verməyə məcbur edir.
        # Bu, kiçik modellərdə "cavabdan əvvəl izah yazmaq" problemini kökündən həll edir.
        # Sxem uyğunluğunu isə sonra PydanticOutputParser yoxlayır.
        format="json" if json_mode else None,
        # reasoning=False -> qwen3 "düşünmə" (<think>) rejimini söndürür.
        # GPU-suz maşında düşünmə tokenləri cavabı 2-4 dəfə uzadır, bizə isə
        # sadəcə struktur JSON lazımdır - burada reasoning dəyər qatmır.
        reasoning=False,
        # Model işi bitəndən qısa müddət sonra RAM-dan boşalsın
        keep_alive=settings.llm_keep_alive,
        # Bütün nüvələri tutmasın ki, maşın cavab verməyi dayandırmasın
        num_thread=settings.llm_num_thread,
        # Cavabın maksimum uzunluğu - model "danışmağa" başlasa kəsilir
        num_predict=num_predict,
        # Kontekst pəncərəsini kiçik saxlayırıq: az RAM, sürətli emal
        num_ctx=settings.llm_num_ctx,
    )


# Hansı Claude modelləri hələ də `temperature` qəbul edir?
#
# BU SİYAHI DEKORASİYA DEYİL - REAL SƏHVDƏN ÇIXIB. İlk sınaqda hər sorğu belə
# cavab verdi:
#     400 invalid_request_error: `temperature` is deprecated for this model.
# Yeni nəsil modellərdə (Opus 5, Sonnet 5, 4.6+) temperature/top_p/top_k
# ÇIXARILIB - göndərilsə sorğu rədd edilir. Nəticə isə görünmür: `with_fallbacks`
# 400-ü də "səhv" sayıb sükutla Ollama-ya keçirdi. Yəni açar düzgün, paket
# quraşdırılmış, .env doğru olsa da, Claude BİR DƏFƏ də işləmirdi - sadəcə hər
# sorğu 4.5 token/saniyəlik Ollama-ya düşürdü. Fallback layihəni ayaqda saxlayır,
# amma səhvi də gizlədir; ona görə konfiqurasiyanı əvvəlcədən düzgün qururuq.
#
# Köhnə modellərdə temperature hələ işləyir, ona görə tam silmirik: kimsə
# .env-də LLM_CLAUDE_MODEL=claude-haiku-4-5 yazsa, determinizm qorunsun.
_TEMPERATURE_SUPPORTED = ("claude-haiku-4-5", "claude-3")


def build_claude(temperature: float, max_tokens: int) -> BaseChatModel:
    """
    Claude API modeli.

    `effort` niyə "low"? Bu layihədə model qısa JSON qaytarır ("süd", "1 l",
    kateqoriya rəqəmi). Dərin düşünmə burada nə dəqiqlik qatır, nə də lazımdır -
    yalnız gecikmə və xərc əlavə edir. Mürəkkəb tapşırıq üçün .env-də
    LLM_CLAUDE_EFFORT=high yazmaq kifayətdir.

    `format="json"` ekvivalenti YOXDUR - Ollama-dakı kimi sintaktik məcburiyyət
    Claude-da fərqli işləyir. Bizim prompt onsuz da "yalnız JSON qaytar" deyir
    və nəticəni parser yoxlayır, ona görə əlavə ayar lazım deyil.

    Temperature niyə şərtlidir? Bax: yuxarıdakı `_TEMPERATURE_SUPPORTED`.
    Yeni modellərdə determinizmi temperature yox, `effort=low` + dəqiq prompt
    verir - praktikada çıxarış nəticələri onsuz da sabit gəlir.
    """
    from langchain_anthropic import ChatAnthropic

    kwargs = {}
    if settings.llm_claude_model.startswith(_TEMPERATURE_SUPPORTED):
        kwargs["temperature"] = temperature

    return ChatAnthropic(
        model=settings.llm_claude_model,
        api_key=settings.anthropic_api_key or None,
        max_tokens=max_tokens,
        output_config={"effort": settings.llm_claude_effort},
        default_request_timeout=settings.llm_claude_timeout,
        # Şəbəkə səhvlərində SDK özü təkrar cəhd edir; ondan sonra fallback işə düşür
        max_retries=2,
        **kwargs,
    )


def claude_enabled() -> bool:
    """
    Claude işlədilə bilərmi?

    Yalnız provider seçilməsi kifayət deyil - açar da olmalıdır. Açarsız
    ChatAnthropic yaradılsa, hər sorğu 401 verib fallback-ə düşərdi: nəticə
    düzgün olardı, amma hər çağırışa boş yerə şəbəkə gecikməsi əlavə edərdi.
    """
    return settings.llm_provider == "claude" and bool(settings.anthropic_api_key)


def get_llm(
    temperature: float | None = None,
    num_predict: int | None = None,
    json_mode: bool = False,
) -> Runnable:
    """
    LCEL zəncirlərində istifadə olunan model.

    Qaytarılan obyekt ya birbaşa ChatOllama, ya da Claude+Ollama fallback
    zənciridir. Hər ikisi eyni Runnable interfeysinə malikdir - çağıran tərəf
    fərqi bilmir və bilməməlidir.
    """
    temperature = temperature if temperature is not None else settings.llm_temperature
    num_predict = num_predict if num_predict is not None else settings.llm_num_predict

    ollama = build_ollama(temperature, num_predict, json_mode=json_mode)
    if not claude_enabled():
        return ollama

    try:
        # DİQQƏT: burada `num_predict` YOX, Claude-un öz limiti verilir.
        # Ollama-nın 32-800 tokenlik limiti Claude üçün azdır: düşünmə tokenləri
        # də həmin tavana daxildir və cavab yarımçıq kəsilə bilər.
        claude = build_claude(temperature, settings.llm_claude_max_tokens)
    except Exception:
        # Paket quraşdırılmayıb və ya konfiqurasiya səhvdir - layihə dayanmamalıdır
        return ollama

    return claude.with_fallbacks([ollama])


def message_text(message) -> str:
    """
    Modelin cavabından TƏMİZ mətni çıxarır.

    NİYƏ AYRICA FUNKSİYA LAZIM OLDU?
    Ollama cavabı sadə sətirdir:
        message.content == '{"n":"süd"}'
    Claude isə blok siyahısı qaytarır - düşünmə (thinking) bloku + mətn bloku:
        message.content == [{"type":"thinking",...}, {"type":"text","text":'{"n":"süd"}'}]
    Bu siyahını birbaşa `json.loads()`-a versək:
        TypeError: the JSON object must be str, bytes or bytearray, not list
    Zəncirdə `.with_retry()` olduğu üçün ikinci cəhd də eyni səhvi verir və sətir
    "uğursuz" sayılıb atılır - yəni Claude-a keçəndə HƏR sətir sükutla itərdi.

    `message.text` LangChain-in öz xüsusiyyətidir: siyahıdan yalnız mətn
    bloklarını yığır, sadə sətri isə olduğu kimi qaytarır. Hər iki model üçün
    eyni işləyir - çağıran tərəf fərqi bilmir.
    """
    text = getattr(message, "text", None)
    if text is None:
        return str(message)
    # `.text` sadə sətir deyil, TextAccessor obyektidir - str() onu mətnə çevirir.
    # Çağırış kimi işlətmək (`text()`) da işləyir, amma köhnəlmiş sayılır.
    return str(text)


def active_model_name() -> str:
    """
    Keş açarı üçün model adı.

    Niyə vacibdir? `ai/cache.py` nəticəni (model, prompt versiyası, mətn)
    üçlüyü ilə keşləyir. İki fərqli model eyni açardan istifadə etsə, Claude-un
    cavabı Ollama-nınki kimi (və əksinə) oxunardı.
    """
    return settings.llm_claude_model if claude_enabled() else settings.ollama_model


def check_llm() -> dict:
    """
    LLM hazırdırmı? /health endpoint-i bunu göstərir.

    Deploy zamanı ən çox lazım olan yoxlamadır: model çəkilməyibsə və ya açar
    yoxdursa, səhv burada görünür - istifadəçi gözləyib boş cavab almır.
    """
    info = {
        "provider": settings.llm_provider,
        "base_url": settings.ollama_base_url,
        "model": settings.ollama_model,
        "reachable": False,
        "model_available": False,
    }

    if settings.llm_provider == "claude":
        info["claude_model"] = settings.llm_claude_model
        info["claude_key_set"] = bool(settings.anthropic_api_key)
        info["claude_active"] = claude_enabled()
        if not settings.anthropic_api_key:
            info["claude_note"] = (
                "ANTHROPIC_API_KEY boşdur - Claude işə düşmür, "
                "yalnız Ollama işlədilir"
            )

    try:
        r = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        r.raise_for_status()
        info["reachable"] = True
        names = [m.get("name", "") for m in r.json().get("models", [])]
        info["installed_models"] = names
        # Dəqiq uyğunluq: "qwen3:4b" quraşdırılıbsa, bu "qwen3:27b" demək DEYİL
        info["model_available"] = settings.ollama_model in names
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"

    # Ollama ehtiyat rolundadır: Claude işləyirsə, onun əlçatmazlığı fəlakət deyil
    if claude_enabled():
        info["status"] = "claude (ehtiyat: ollama)" if info["reachable"] else "claude"
    else:
        info["status"] = "ollama"

    return info


if __name__ == "__main__":
    import json
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(check_llm(), ensure_ascii=False, indent=2))
