"""
SƏHƏR HESABATI — «gecə n8n nə etdi?»

NİYƏ LAZIMDIR? Gündəlik axın hər səhər 07:00-da işləyir və nəticəsi
n8n-in icra tarixçəsində qalır. Ora baxmaq üçün brauzer açmaq, workflow
tapmaq, icranı seçmək lazımdır - yəni praktikada heç kim baxmır. Bu skript
həmin sualın cavabını BİR FAYLA yazır.

BULUD AGENTİ BU İŞİ GÖRƏ BİLMİR (yoxlanıldı 2026-09-10): bulud routine-i
`data/basketiq.db`-yə, `127.0.0.1:8000`-ə və Docker-dəki n8n-ə çata bilmir,
layihənin git remote-u da yoxdur. Ona görə yoxlama YERLİDİR - Task Scheduler
ilə işləyir, eynilə serverin özü kimi.

İSTİFADƏ:
    python -m tools.morning_report              # ekrana
    python -m tools.morning_report --write      # logs/morning.md faylına
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_connection  # noqa: E402
from app.stores import MARKETS, market_for  # noqa: E402
from ingestion.profiles import profile_for  # noqa: E402

RAPORT = Path(__file__).resolve().parent.parent / "logs" / "morning.md"


def _sətirlər(conn, bugün: str, dünən: str) -> list[str]:
    out: list[str] = [f"# Səhər hesabatı — {bugün}", ""]

    # --- 1. Axın işlədimi? ---------------------------------------------------
    # SÜBUT `source_probes`-dur: yoxlama qolu HƏR GÜN işləyir, kataloq qolundan
    # fərqli olaraq. Kataloq qolu «yeni kataloq yoxdur» ilə bitsə də, yoxlama
    # sətri yazılmalıdır. Sətir yoxdursa, axın ÜMUMİYYƏTLƏ işləməyib.
    probe_bugün = conn.execute(
        "SELECT slug, alive, note, checked_at FROM source_probes "
        "WHERE date(checked_at) = ? ORDER BY slug",
        (bugün,),
    ).fetchall()

    if probe_bugün:
        out += ["## Axın işlədi ✓", "", f"Bu gün {len(probe_bugün)} mənbə yoxlanılıb.", ""]
    else:
        out += [
            "## AXIN İŞLƏMƏYİB ✗",
            "",
            "Bu gün üçün heç bir yoxlama qeydi yoxdur. Ehtimal olunan səbəblər:",
            "",
            "- BasketIQ serveri 07:00-da işləmirdi (`Get-ScheduledTaskInfo -TaskName 'BasketIQ Server'`)",
            "- n8n konteyneri dayanıb (`docker ps | grep n8n`)",
            "- Workflow deaktivdir (<http://localhost:5678>)",
            "",
        ]

    # --- 2. Bağlı mənbələr ---------------------------------------------------
    out += ["## Gözlənilən mənbələr", ""]
    gözlənilən = 0
    for market in MARKETS:
        profile = profile_for(market.slug)
        # MARKETİN İKİ MƏNBƏYİ VAR və `status` yalnız BİRİNƏ aiddir.
        #
        # BU SƏHV BURADA BİR DƏFƏ EDİLDİ: filtr `status != active` idi və
        # hesabat «Bravo Market QAYITDI 🎉» yazdı. Halbuki Bravonun status-u
        # KATALOQ mənbəyinə aiddir (onun kataloqu yoxdur), mağaza mənbəyi isə
        # işləyir və 13 min məhsulu məhz oradan gəlir. Yalançı həyəcan
        # hesabatı dəyərsizləşdirir - adam ona inanmağı dayandırır.
        #
        # DÜZGÜN ŞƏRT: heç bir işləyən mənbəsi olmayan market.
        if profile is None or profile.scrapeable or profile.shoppable:
            continue
        gözlənilən += 1
        row = conn.execute(
            "SELECT alive, note, checked_at FROM source_probes "
            "WHERE slug = ? ORDER BY checked_at DESC LIMIT 1",
            (market.slug,),
        ).fetchone()
        if row is None:
            out.append(f"- **{market.name}** — hələ yoxlanılmayıb")
            continue

        # DƏYİŞİKLİK ƏSAS XƏBƏRDİR: hər gün eyni cavab səsə çevrilir, ona görə
        # yalnız fərq vurğulanır.
        if row["alive"]:
            neçə = conn.execute(
                "SELECT COUNT(*) FROM source_probes WHERE slug = ? AND alive = 0",
                (market.slug,),
            ).fetchone()[0]
            out.append(
                f"- **{market.name} — QAYITDI 🎉** ({row['note']}). "
                f"Bundan əvvəl {neçə} gün bağlı idi. "
                f"`ingestion/profiles.py`-də `status` yenilənməlidir."
            )
        else:
            bağlı = conn.execute(
                "SELECT COUNT(*) FROM source_probes WHERE slug = ? AND alive = 0",
                (market.slug,),
            ).fetchone()[0]
            out.append(
                f"- {market.name} — dəyişiklik yoxdur ({row['note']}, {bağlı} gündür)"
            )
    if not gözlənilən:
        out.append("Gözlənilən mənbə yoxdur — dörd marketin hamısı işləyir.")
    out.append("")

    # --- 3. Data dəyişikliyi -------------------------------------------------
    yeni_kataloq = conn.execute(
        "SELECT id, store_id, file_path FROM catalogs WHERE date(ingested_at) = ?"
        if _sütun_var(conn, "catalogs", "ingested_at")
        else "SELECT id, store_id, file_path FROM catalogs WHERE 0",
        (bugün,) if _sütun_var(conn, "catalogs", "ingested_at") else (),
    ).fetchall()

    yeni_qiymət = conn.execute(
        "SELECT COUNT(*) FROM prices WHERE date(seen_at) = ?", (bugün,)
    ).fetchone()[0]
    yeni_snapshot = conn.execute(
        "SELECT COUNT(*) FROM price_snapshots WHERE date(observed_at) = ?", (bugün,)
    ).fetchone()[0]
    dünənki_snapshot = conn.execute(
        "SELECT COUNT(*) FROM price_snapshots WHERE date(observed_at) = ?", (dünən,)
    ).fetchone()[0]

    out += [
        "## Bu gün gələn data",
        "",
        f"- yeni kataloq: **{len(yeni_kataloq)}**",
        f"- yeni kataloq qiyməti: **{yeni_qiymət}**",
        f"- mağaza snapshot-u: **{yeni_snapshot}** (dünən {dünənki_snapshot})",
        "",
    ]

    # --- 4. Market vəziyyəti -------------------------------------------------
    out += ["## Marketlər", "", "| Market | Məhsul | Nişanlı sətir |", "|---|---|---|"]
    for row in conn.execute(
        """
        SELECT s.slug AS slug,
               COUNT(DISTINCT pr.product_id) AS products,
               SUM(CASE WHEN pr.flags IS NOT NULL THEN 1 ELSE 0 END) AS flagged
        FROM stores s LEFT JOIN prices pr ON pr.store_id = s.id GROUP BY s.id
        """
    ):
        market = market_for(row["slug"])
        if market is None or not row["products"]:
            continue
        out.append(f"| {market.name} | {row['products']} | {row['flagged'] or 0} |")
    out.append("")

    out += ["---", "", "Ətraflı: <http://localhost:5678> (n8n icra tarixçəsi) · "
            "`curl http://127.0.0.1:8000/api/scrape/bazar-store/probe/history`"]
    return out


def _sütun_var(conn, cədvəl: str, sütun: str) -> bool:
    """Sxem versiyaları arasında fərq ola bilər - sütunun varlığını yoxlayırıq."""
    return any(r[1] == sütun for r in conn.execute(f"PRAGMA table_info({cədvəl})"))


def main() -> int:
    parser = argparse.ArgumentParser(description="BasketIQ səhər hesabatı")
    parser.add_argument("--write", action="store_true", help="logs/morning.md faylına yaz")
    args = parser.parse_args()

    bugün = date.today().isoformat()
    dünən = (date.today() - timedelta(days=1)).isoformat()

    conn = get_connection()
    try:
        mətn = "\n".join(_sətirlər(conn, bugün, dünən)) + "\n"
    finally:
        conn.close()

    if args.write:
        RAPORT.parent.mkdir(parents=True, exist_ok=True)
        RAPORT.write_text(mətn, encoding="utf-8")
        print(f"yazıldı: {RAPORT}")
    else:
        print(mətn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
