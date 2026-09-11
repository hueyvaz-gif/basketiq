"""
Məhsul uyğunlaşdırma endpoint-ləri.

ADMİN QAPISININ ARXASINDADIR (2026-09-11). Əvvəl açıq idi, halbuki `/run`
bazanı DƏYİŞİR (qrupları birləşdirir) və pullu LLM-i çağırır — ünvanı bilən
hər kəs bunu edə bilərdi. Onu çağıran yeganə səhifə `/admin`-dir (`admin.js`),
ona görə istifadəçi səthindən heç nə itmir. Qapının mənası `app/security.py`-dədir.
"""

from fastapi import APIRouter, Depends

from ai.matcher import find_candidates, load_groups, load_products, run_matching
from app.security import require_admin

router = APIRouter(prefix="/api/match", tags=["match"], dependencies=[Depends(require_admin)])


@router.get("/candidates")
def candidates():
    """
    LLM-siz namizəd siyahısı - ucuz pillənin nə tapdığını göstərir.

    Bunu əvvəlcə baxmaq faydalıdır: LLM-ə neçə cüt gedəcəyini
    və nə qədər vaxt aparacağını əvvəlcədən bilirsən.
    """
    products = load_products()
    found = find_candidates(products)
    return {
        "products": len(products),
        "candidates": [
            {"a": c.a_text, "b": c.b_text, "similarity": c.similarity} for c in found
        ],
    }


@router.post("/run")
def run(limit: int = 20, use_cache: bool = True, dry_run: bool = False):
    """
    Üç pilləli uyğunlaşdırma: barkod -> oxşarlıq -> LLM (yalnız şübhəlilər).

    `dry_run=true` — LLM çağırılmır, baza dəyişmir: neçə cütün avtomatik
    birləşəcəyini və neçəsinin LLM-ə gedəcəyini əvvəlcədən göstərir.
    """
    return run_matching(limit=limit, use_cache=use_cache, dry_run=dry_run)


@router.get("/groups")
def groups():
    """Birdən çox məhsulu olan qruplar."""
    return {"groups": load_groups()}
