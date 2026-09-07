"""
Real səs faylını uçdan-uca yoxlayır: audio -> mətn -> əmr -> cavab.

İstifadə:
    python tools/voice_check.py qeyd.ogg
    python tools/voice_check.py qeyd.wav --model base
    python tools/voice_check.py --text "səbətə iki litr süd əlavə et"

Niyə ayrıca alət? Whisper testlərdə mock edilir (model 460 MB-dır və hər
çağırış 10+ saniyə çəkir). Amma modelin REAL səsdə necə işlədiyini görmək
lazımdır - xüsusən Azərbaycan dilində. Bu alət məhz onun üçündür.

Səs faylını haradan almalı? Telegram-da özünə səs mesajı göndər, sonra
"Save as..." ilə .ogg kimi yadda saxla. Və ya telefonun diktofonu.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from voice.actions import run  # noqa: E402
from voice.commands import parse, parse_regex  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Səs əmrini uçdan-uca yoxla")
    ap.add_argument("audio", nargs="?", help="səs faylı (.ogg, .wav, .mp3, .m4a)")
    ap.add_argument("--text", help="səsi keç, birbaşa mətni yoxla")
    ap.add_argument("--model", help="Whisper modeli (tiny/base/small)")
    ap.add_argument("--no-llm", action="store_true", help="LLM ehtiyat yolunu söndür")
    ap.add_argument("--dry-run", action="store_true", help="əmri İCRA ETMƏ, yalnız təhlil")
    args = ap.parse_args()

    if not args.audio and not args.text:
        ap.print_help()
        raise SystemExit(1)

    if args.text:
        text = args.text
    else:
        path = Path(args.audio)
        if not path.is_file():
            print(f"Fayl tapılmadı: {path}")
            raise SystemExit(1)

        if args.model:
            from app.config import settings

            settings.whisper_model = args.model

        from voice.transcribe import get_model, transcribe

        print(f"Model yüklənir ({args.model or 'defolt'})...")
        t0 = time.time()
        get_model()
        print(f"  yükləndi: {time.time() - t0:.1f} san")

        result = transcribe(path.read_bytes())
        print(f"\nAudio   : {result.duration:.1f} san")
        print(f"Emal    : {result.elapsed:.1f} san  (model: {result.model})")
        print(f"Dil     : {result.language}")
        print(f"Mətn    : «{result.text}»")
        text = result.text

    if not text:
        print("\nMətn boşdur - əmr təhlil edilmir.")
        return

    regex_command = parse_regex(text)
    print(f"\nRegex   : {regex_command.intent}"
          f"  query={regex_command.query!r}  qty={regex_command.qty:g}")

    command = parse(text, use_llm=not args.no_llm)
    if command.source == "llm":
        print(f"LLM     : {command.intent}"
              f"  query={command.query!r}  qty={command.qty:g}")
    if command.note:
        print(f"Qeyd    : {command.note}")

    if args.dry_run:
        print("\n(--dry-run: əmr icra edilmədi)")
        return

    print("\nCavab:")
    print("  " + run(command).replace("\n", "\n  "))


if __name__ == "__main__":
    main()
