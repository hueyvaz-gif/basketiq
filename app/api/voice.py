"""
Səs əmri endpoint-ləri.

İki giriş var və bu, qəsdəndir:

  POST /api/voice        audio faylı  -> mətn -> əmr -> cavab
  POST /api/voice/text   hazır mətn   ->        əmr -> cavab

Niyə mətn variantı? Çünki zəncirin iki hissəsi tamam fərqli səbəblərdən
qırılır: Whisper səsi səhv oxuya bilər, təhlil isə düzgün mətni səhv başa
düşə bilər. Ayrı endpoint olmasa, "niyə işləmədi?" sualına cavab tapmaq üçün
hər dəfə mikrofona danışmaq lazım gələrdi.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings

from voice.actions import run
from voice.commands import parse

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Səs əmri qısadır. 10 MB-dan böyük fayl ya səhvdir, ya sui-istifadə -
# hər halda Whisper-i onunla yükləmək mənasızdır.
MAX_AUDIO_MB = 10


@router.post("")
async def voice_command(file: UploadFile = File(...), use_llm: bool | None = Form(None)):
    """Səs faylı -> transkript + icra olunmuş əmrin cavabı."""
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "Audio boşdur")

    size_mb = len(audio) / (1024 * 1024)
    if size_mb > MAX_AUDIO_MB:
        raise HTTPException(413, f"Audio çox böyükdür: {size_mb:.1f} MB")

    try:
        from voice.transcribe import transcribe

        result = transcribe(audio)
    except ModuleNotFoundError:
        # Səs bonusu ayrıca quraşdırılır (image-i 684 MB -> 1.25 GB edir).
        # Xəta mətni nə etmək lazım olduğunu BİRBAŞA deməlidir.
        raise HTTPException(
            503,
            "Səs modulu quraşdırılmayıb. Quraşdırmaq üçün: "
            "pip install -r requirements-voice.txt  "
            "(Docker: --build-arg WITH_VOICE=true)",
        )
    except Exception as e:
        # Model endirilməyə və ya audio format açılmaya bilər - bu, 500 deyil,
        # konfiqurasiya məsələsidir və istifadəçiyə aydın deyilməlidir.
        raise HTTPException(503, f"Səs tanınmadı: {type(e).__name__}: {e}")

    if use_llm is None:
        use_llm = settings.voice_llm_fallback
    command = parse(result.text, use_llm=use_llm)
    return {
        "transcript": result.as_dict(),
        "command": command.as_dict(),
        "reply": run(command),
    }


@router.post("/text")
def text_command(text: str = Form(...), use_llm: bool | None = Form(None)):
    """Mətn əmri - səsi keçib yalnız təhlili yoxlamaq üçün."""
    if use_llm is None:
        use_llm = settings.voice_llm_fallback
    command = parse(text, use_llm=use_llm)
    return {"command": command.as_dict(), "reply": run(command)}
