"""
LLM nəticələrinin sadə disk keşi.

NİYƏ BU LAYİHƏDƏ MƏCBURİDİR:
Sənin maşınında GPU yoxdur - bir sətrin emalı bir neçə saniyə çəkir.
Prompt-u düzəldib pipeline-ı 10-cu dəfə işlədəndə eyni sətirləri yenidən
hesablamaq saatlar deməkdir.

Keş açarı = model adı + prompt versiyası + sətrin özü.
Yəni model və ya prompt dəyişəndə keş özü-özünə etibarsız olur.
"""

import hashlib
import json
from pathlib import Path

from app.config import settings

CACHE_DIR = settings.data_dir / "cache" / "extract"


def cache_key(model: str, prompt_version: str, text: str) -> str:
    payload = f"{model}||{prompt_version}||{text.strip().lower()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get(key: str) -> dict | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Korlanmış keş faylı sistemi dayandırmamalıdır - sadəcə yenidən hesablayırıq
        path.unlink(missing_ok=True)
        return None


def put(key: str, value: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    # Əvvəlcə müvəqqəti fayla yazırıq: proses yarıda kəsilsə yarımçıq JSON qalmasın
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def stats() -> dict:
    if not CACHE_DIR.exists():
        return {"entries": 0, "size_kb": 0}
    files = list(CACHE_DIR.glob("*.json"))
    return {
        "entries": len(files),
        "size_kb": round(sum(f.stat().st_size for f in files) / 1024, 1),
    }


def clear() -> int:
    """Keşi tamamilə silir. Prompt üzərində işləyərkən lazım ola bilər."""
    if not CACHE_DIR.exists():
        return 0
    files = list(CACHE_DIR.glob("*.json"))
    for f in files:
        f.unlink(missing_ok=True)
    return len(files)


if __name__ == "__main__":
    print(stats())
