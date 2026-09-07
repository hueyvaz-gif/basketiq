"""
Ollama çağırışının vaxtını hissə-hissə göstərir: prompt emalı vs cavab yazma.

    python tools/profile_llm.py

Niyə lazımdır? "Yavaşdır" deyib təsadüfi parametr dəyişmək vaxt itkisidir.
Ollama hər cavabda dəqiq ölçü qaytarır - onu oxuyuruq və hansı hissəni
optimallaşdırmağın mənası olduğunu görürük.
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.chains import CATEGORY_LIST_TEXT  # noqa: E402
from ai.prompts import COMPACT_FORMAT_INSTRUCTIONS, EXTRACTION_PROMPT  # noqa: E402
from app.config import settings  # noqa: E402

LINE = "Süd Milla 2.5% 1L 1,89 2,45"

# Zəncirdə istifadə olunan PROMPT-un EYNİSİ - başqa mətn ölçsək, ölçü yalan olar
PROMPT = EXTRACTION_PROMPT.partial(
    format_instructions=COMPACT_FORMAT_INSTRUCTIONS,
    categories=CATEGORY_LIST_TEXT,
)


def call(messages: list[dict]) -> dict:
    res = requests.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": messages,
            "format": "json",
            "think": False,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_ctx": settings.llm_num_ctx,
                "num_thread": settings.llm_num_thread,
                "num_predict": settings.llm_num_predict,
            },
        },
        timeout=600,
    )
    res.raise_for_status()
    return res.json()


def as_dicts(line: str) -> list[dict]:
    role_map = {"system": "system", "human": "user", "ai": "assistant"}
    return [
        {"role": role_map.get(m.type, "user"), "content": m.content}
        for m in PROMPT.format_messages(line=line)
    ]


def report(label: str, data: dict, items: int = 1) -> None:
    ns = 1_000_000_000
    p_eval = data.get("prompt_eval_duration", 0) / ns
    p_count = data.get("prompt_eval_count", 0)
    eval_d = data.get("eval_duration", 0) / ns
    e_count = data.get("eval_count", 0)
    total = data.get("total_duration", 0) / ns

    print(f"\n=== {label} ===")
    print(f"  prompt emalı    : {p_eval:6.2f} san  ({p_count} token, "
          f"{p_count / p_eval if p_eval else 0:.0f} tok/san)")
    print(f"  cavab yazılması : {eval_d:6.2f} san  ({e_count} token, "
          f"{e_count / eval_d if eval_d else 0:.1f} tok/san)")
    print(f"  CƏMİ            : {total:6.2f} san   ({total / items:.1f} san/sətir)")
    print(f"  cavab: {data['message']['content'][:200]!r}")


def main() -> None:
    print(f"model={settings.ollama_model}  num_ctx={settings.llm_num_ctx}")
    messages = as_dicts(LINE)
    print(f"system prompt: {len(messages[0]['content'])} simvol")

    call(messages)  # qızdırma
    report("real zəncir prompt-u", call(messages))


if __name__ == "__main__":
    main()
