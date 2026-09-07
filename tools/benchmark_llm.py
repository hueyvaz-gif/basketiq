"""
LLM sürətini ölçür.

    python tools/benchmark_llm.py

Niyə lazımdır? "Yavaşdır" hissiyyatdır, "37 saniyə/sətir" rəqəmdir.
Optimallaşdırmanın işlədiyini yalnız ölçməklə bilmək olar.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.chains import extract_attributes  # noqa: E402
from app.config import settings  # noqa: E402

LINES = [
    "Süd Milla 2.5% 1L 1,89 2,45",
    "Günəbaxan yağı Sola 1.8 L 6,20",
    "Makaron Barilla 500 q 2.10",
    "Şəkər Tozu 1 kq 1,45",
]


def run(label: str, lines: list[str]) -> float:
    started = time.time()
    report = extract_attributes(lines, use_cache=False)
    elapsed = time.time() - started
    per_line = elapsed / len(lines)
    print(f"{label:<28} {elapsed:6.1f} san   {per_line:5.1f} san/sətir   "
          f"uğursuz={report.failed}")
    return per_line


def main() -> None:
    print(f"model={settings.ollama_model}  concurrency={settings.llm_max_concurrency}")
    print("-" * 70)

    # Modeli RAM-a qaldırmaq üçün boş çağırış - onu ölçüyə salmırıq
    print("modeli qızdırırıq...")
    extract_attributes(LINES[:1], use_cache=False)

    run("qızdırıldıqdan sonra (1)", LINES[:1])
    run("4 sətir", LINES)

    print("-" * 70)
    started = time.time()
    extract_attributes(LINES, use_cache=True)   # birinci dəfə keşə yazır
    first = time.time() - started
    started = time.time()
    extract_attributes(LINES, use_cache=True)   # ikinci dəfə keşdən oxuyur
    second = time.time() - started
    print(f"keş ilə 1-ci dəfə: {first:.1f} san   2-ci dəfə: {second:.3f} san")


if __name__ == "__main__":
    main()
