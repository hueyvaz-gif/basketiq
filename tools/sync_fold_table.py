"""
Fold cədvəlini Python-dan JS-ə köçürür (M0).

    python -m tools.sync_fold_table          # fərqi göstərir
    python -m tools.sync_fold_table --apply  # JS faylını yenidən yazır

NİYƏ ALƏT, ƏL İLƏ REDAKTƏ YOX? Cədvəl iki fayldadır (Python + JS), çünki
brauzer Python işlədə bilmir. İki nüsxə isə vaxtla ayrılır - biri yenilənir,
digəri unudulur və axtarış brauzerdə bir cür, serverdə başqa cür işləyir.
Belə fərq SƏSSİZDİR: hər iki tərəf «işləyir», sadəcə nəticələr fərqlidir.

Qoruma iki qatlıdır: bu alət düzəldir, `tests/test_search_norm.py` isə
fərqi tutur (yəni alət işlədilməsə də səhv üzə çıxır).
"""

import argparse
import io
import sys
from pathlib import Path

from app.search_norm import FOLD_MAP

JS_PATH = Path(__file__).resolve().parent.parent / "app" / "static" / "search-norm.js"
BAŞLANĞIC = "// --- FOLD_MAP başlanğıc (avtomatik yazılır) ---"
SON = "// --- FOLD_MAP son ---"


def render() -> str:
    """Python cədvəlindən JS bloku qurur - sıra Python-dakı sıradır."""
    sətirlər = ["const FOLD_MAP = {"]
    # Eyni ASCII hərfə düşən variantlar YAN-YANA yazılır: cədvələ baxan adam
    # «ə və Ə hər ikisi e-dir» faktını bir sətirdə görür.
    qruplar: dict[str, list[str]] = {}
    for hərf, ascii_hərf in FOLD_MAP.items():
        qruplar.setdefault(ascii_hərf, []).append(hərf)

    for ascii_hərf, hərflər in qruplar.items():
        cüt = ", ".join(f'"{h}": "{ascii_hərf}"' for h in hərflər)
        sətirlər.append(f"  {cüt},")
    sətirlər.append("};")
    return "\n".join(sətirlər)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fold cədvəlini JS-ə köçürür")
    parser.add_argument("--apply", action="store_true", help="JS faylını yaz")
    args = parser.parse_args()

    mətn = io.open(JS_PATH, encoding="utf-8").read()
    baş = mətn.index(BAŞLANĞIC) + len(BAŞLANĞIC)
    son = mətn.index(SON)

    cari = mətn[baş:son].strip()
    yeni = render()

    if cari == yeni:
        print("Cədvəllər eynidir - dəyişiklik lazım deyil.")
        return 0

    print("FƏRQ VAR:\n--- JS-dəki ---")
    print(cari)
    print("--- Python-dan ---")
    print(yeni)

    if not args.apply:
        print("\nBu, ÖN BAXIŞDIR. Yazmaq üçün: --apply")
        return 1

    io.open(JS_PATH, "w", encoding="utf-8").write(
        mətn[:baş] + "\n" + yeni + "\n" + mətn[son:]
    )
    print("\nJS faylı yeniləndi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
