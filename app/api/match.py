"""Məhsul uyğunlaşdırma endpoint-ləri."""

from fastapi import APIRouter

from ai.matcher import find_candidates, load_groups, load_products, run_matching

router = APIRouter(prefix="/api/match", tags=["match"])


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
def run(limit: int = 20, use_cache: bool = True):
    """Namizədləri LLM ilə yoxlayır və təsdiqlənənləri qruplara birləşdirir."""
    return run_matching(limit=limit, use_cache=use_cache)


@router.get("/groups")
def groups():
    """Birdən çox məhsulu olan qruplar."""
    return {"groups": load_groups()}
