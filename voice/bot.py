"""
Telegram botu — səs mesajı göndərirsən, cavabı mətnlə alırsan.

NİYƏ KİTABXANA YOX, ADİ `requests`?
`python-telegram-bot` güclü çərçivədir, amma bu bota cəmi üç metod lazımdır:
getUpdates, getFile, sendMessage. Çərçivə əlavə asılılıq, öz async modeli və
öyrənmə yükü gətirər, əvəzində bizə heç nə verməz. Üstəlik Telegram API-nin
necə işlədiyi bu kodda AÇIQ görünür - tədris layihəsi üçün bu, üstünlükdür.

NİYƏ LONG POLLING, WEBHOOK YOX?
Webhook üçün internetdən əlçatan HTTPS ünvan lazımdır. Lokal maşında bu, ya
ngrok, ya port yönləndirmə deməkdir. Long polling isə heç nə tələb etmir -
bot özü Telegram-dan soruşur. DigitalOcean-a çıxandan sonra webhook-a keçmək
olar; kod dəyişikliyi kiçikdir.

İŞƏ SALMAQ:
    .env -> TELEGRAM_BOT_TOKEN=...      (@BotFather-dən alınır)
    python -m voice.bot

GÖZLƏNTİ (bu maşında ölçülüb):
    model yüklənməsi   ~33 san (yalnız ilk mesajda)
    3-4 saniyəlik səs  ~10 san emal
Ona görə bot dərhal "səsi dinləyirəm..." yazır - istifadəçi botun donduğunu
düşünməsin.
"""

import sys
import time

import requests

from app.config import settings
from voice.actions import run
from voice.commands import parse

API = "https://api.telegram.org/bot{token}/{method}"
FILE_API = "https://api.telegram.org/file/bot{token}/{path}"

# Telegram getUpdates sorğusunu bu qədər saniyə AÇIQ SAXLAYIR və yeni mesaj
# gələn kimi cavab verir. Yəni 30 saniyəlik gecikmə deyil - əksinə, boş
# sorğuların sayını azaldan mexanizmdir.
POLL_TIMEOUT = 30

MAX_VOICE_MB = 10


class TelegramError(RuntimeError):
    pass


def _call(method: str, **params):
    token = settings.telegram_bot_token
    if not token:
        raise TelegramError(
            "TELEGRAM_BOT_TOKEN boşdur. @BotFather-dən token al və .env-ə yaz."
        )
    response = requests.post(
        API.format(token=token, method=method),
        json=params,
        timeout=POLL_TIMEOUT + 15,
    )
    data = response.json()
    if not data.get("ok"):
        raise TelegramError(f"{method}: {data.get('description')}")
    return data["result"]


def send(chat_id: int, text: str) -> None:
    _call("sendMessage", chat_id=chat_id, text=text)


def download_voice(file_id: str) -> bytes:
    """
    Telegram-dan səs faylını endirir.

    İki addımlıdır: əvvəlcə getFile ilə müvəqqəti yol alınır, sonra fayl
    ayrı ünvandan endirilir. Telegram API-si məhz belədir.
    """
    info = _call("getFile", file_id=file_id)
    size = info.get("file_size") or 0
    if size > MAX_VOICE_MB * 1024 * 1024:
        raise TelegramError(f"Səs faylı çox böyükdür: {size / 1024 / 1024:.1f} MB")

    url = FILE_API.format(token=settings.telegram_bot_token, path=info["file_path"])
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


HELP = (
    "BasketIQ səsli köməkçi.\n\n"
    "Səs mesajı göndər və ya yaz:\n"
    "• «səbətə iki litr süd əlavə et»\n"
    "• «səbətim harada ucuzdur»\n"
    "• «düyü neçəyədir»\n"
    "• «səbətimdə nə var»\n"
    "• «səbətdən südü çıxar»"
)


def handle(update: dict) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = message["chat"]["id"]

    if "voice" in message or "audio" in message:
        media = message.get("voice") or message["audio"]
        send(chat_id, "Səsi dinləyirəm…")
        try:
            audio = download_voice(media["file_id"])
            from voice.transcribe import transcribe

            result = transcribe(audio)
        except Exception as e:
            send(chat_id, f"Səsi tanıya bilmədim: {type(e).__name__}: {e}")
            return

        if not result.text:
            send(chat_id, "Səsdə mətn tapılmadı - bir də cəhd et.")
            return

        # Transkripti HƏMİŞƏ göstəririk. Whisper səhv oxusa, istifadəçi
        # səbəbi dərhal görür - "bot məni başa düşmür" sualı yaranmır.
        send(chat_id, f"Eşitdim: «{result.text}»")
        text = result.text

    elif "text" in message:
        text = message["text"].strip()
        if text.startswith("/start") or text.startswith("/help"):
            send(chat_id, HELP)
            return
    else:
        send(chat_id, "Yalnız mətn və səs mesajı başa düşürəm.")
        return

    command = parse(text, use_llm=settings.voice_llm_fallback)
    send(chat_id, run(command))


def poll() -> None:
    offset = None
    print("Bot işləyir. Dayandırmaq üçün Ctrl+C.")

    while True:
        try:
            updates = _call("getUpdates", offset=offset, timeout=POLL_TIMEOUT)
        except TelegramError as e:
            print(f"Telegram xətası: {e}")
            time.sleep(5)
            continue
        except requests.RequestException as e:
            print(f"Şəbəkə xətası: {type(e).__name__} - 5 saniyə sonra təkrar")
            time.sleep(5)
            continue

        for update in updates:
            # offset ƏVVƏLCƏ yenilənir: mesajın emalı xəta versə də, həmin
            # mesaj sonsuz döngəyə düşməməlidir.
            offset = update["update_id"] + 1
            try:
                handle(update)
            except Exception as e:
                print(f"Mesaj emal olunmadı: {type(e).__name__}: {e}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not settings.telegram_bot_token:
        print(
            "TELEGRAM_BOT_TOKEN boşdur.\n"
            "1. Telegram-da @BotFather-ə yaz, /newbot əmri ilə bot yarat\n"
            "2. Aldığın tokeni .env faylına yaz: TELEGRAM_BOT_TOKEN=...\n"
            "3. Bu skripti yenidən işə sal"
        )
        raise SystemExit(1)

    poll()


if __name__ == "__main__":
    main()
