"""
Səs -> mətn (Whisper).

NİYƏ `faster-whisper`, RƏSMİ `openai-whisper` DEYİL?
İki konkret səbəb, hər ikisi bu maşında yoxlanılıb:

  1. `openai-whisper` PyTorch tələb edir - təxminən 2.5 GB endirmə.
     `faster-whisper` CTranslate2 üzərində işləyir, torch lazım deyil.
  2. `openai-whisper` audio-nu açmaq üçün sistemdə `ffmpeg` PROQRAMI istəyir.
     Bu maşında ffmpeg yoxdur. `faster-whisper` PyAV işlədir - ffmpeg
     kitabxanaları paketin içindədir, ayrıca quraşdırma lazım deyil.

Model eynidir (OpenAI Whisper çəkiləri), yalnız icra mühiti fərqlidir.

MODEL BİR DƏFƏ YÜKLƏNİR.
Modelin RAM-a yüklənməsi saniyələr çəkir. Hər səs mesajında yenidən yükləsək,
istifadəçi hər dəfə həmin gecikməni ödəyər. Ona görə nüsxə modul səviyyəsində
saxlanılır (lazy singleton).

ÖLÇÜ SEÇİMİ:
  tiny   ~75 MB   - sürətli, Azərbaycan dilində zəif
  base   ~145 MB  - kompromis
  small  ~460 MB  - defolt; GPU-suz maşında qısa mesajda məqbul
Böyük modellər (medium/large) bu maşında praktiki deyil.
"""

import io
import time
from dataclasses import dataclass

from app.config import settings

_model = None
_model_name: str | None = None


@dataclass
class Transcript:
    text: str
    language: str = ""
    duration: float = 0.0        # audio uzunluğu (saniyə)
    elapsed: float = 0.0         # emal nə qədər çəkdi
    model: str = ""

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "duration": round(self.duration, 1),
            "elapsed": round(self.elapsed, 1),
            "model": self.model,
        }


def get_model():
    """
    Modeli bir dəfə yükləyir və saxlayır.

    compute_type="int8": GPU-suz maşında ən sürətli variant. Dəqiqlik bir
    qədər aşağı düşür, amma qısa əmr cümlələrində fərq nəzərə çarpmır -
    onsuz da nəticəni regex təhlil edir, sözbəsöz dəqiqlik tələb olunmur.
    """
    global _model, _model_name

    if _model is not None and _model_name == settings.whisper_model:
        return _model

    from faster_whisper import WhisperModel

    _model = WhisperModel(
        settings.whisper_model,
        device="cpu",
        compute_type="int8",
        cpu_threads=settings.llm_num_thread,
    )
    _model_name = settings.whisper_model
    return _model


def transcribe(audio: bytes, language: str | None = "az") -> Transcript:
    """
    Audio baytları -> mətn.

    language="az" defoltdur: dili özü tapmağa çalışsa, qısa mesajda çox vaxt
    türk və ya rus seçir və nəticə korlanır. Dili qeyd etmək həm sürətli,
    həm dəqiqdir. None versək avtomatik təyin olunur.
    """
    if not audio:
        raise ValueError("Audio boşdur")

    model = get_model()
    started = time.monotonic()

    segments, info = model.transcribe(
        io.BytesIO(audio),
        language=language,
        # beam_size=1 = greedy. CPU-da 5-lik beam 3-4 dəfə yavaşdır və
        # qısa əmr cümlələrində nəticəni praktiki olaraq dəyişmir.
        beam_size=1,
        vad_filter=True,          # sükutu atır - qısa əmrdə xeyli sürət verir
    )

    text = " ".join(segment.text.strip() for segment in segments).strip()

    return Transcript(
        text=text,
        language=getattr(info, "language", "") or "",
        duration=getattr(info, "duration", 0.0) or 0.0,
        elapsed=time.monotonic() - started,
        model=settings.whisper_model,
    )
