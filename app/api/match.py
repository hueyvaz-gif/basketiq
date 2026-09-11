"""
Məhsul uyğunlaşdırma endpoint-ləri.

ADMİN QAPISININ ARXASINDADIR (2026-09-11). Əvvəl açıq idi, halbuki `/run`
bazanı DƏYİŞİR (qrupları birləşdirir) və pullu LLM-i çağırır — ünvanı bilən
hər kəs bunu edə bilərdi. Onu çağıran yeganə səhifə `/admin`-dir (`admin.js`),
ona görə istifadəçi səthindən heç nə itmir. Qapının mənası `app/security.py`-dədir.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai.matcher import decide, find_candidates, load_groups, load_products, run_matching
from app.match_review import pair_state, review_queue
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


@router.get("/review")
def review(status: str = "pending", limit: int = 30):
    """
    İnsan yoxlaması növbəsi (`/admin/matches`, ADDIM 5).

    status=pending — maşın qərar verə bilmədi (ölçü bilinmir);
    status=llm     — LLM qərar verib, insan hələ təsdiqləməyib.
    """
    try:
        return review_queue(status=status, limit=max(1, min(limit, 200)))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


class DecisionIn(BaseModel):
    a_id: int
    b_id: int
    same: bool


@router.post("/decide")
def decide_pair(body: DecisionIn):
    """
    İNSAN qərarı: «bəli, eynidir» / «xeyr, ayrıdır». Hər şeyin üstündədir
    və növbəti maşın qaçışı onu dəyişmir.

    `applied=false` qayıda bilər: insan «bəli» deyib, amma birləşmə qadağaya
    düşüb (eyni marketin iki məhsulu və ya iki fərqli ölçü bir qrupda olardı).
    Qərar yenə YAZILIR — sadəcə ekran bunu gizlətməməlidir, əks halda adam
    «birləşdirdim» düşünər, səbət isə dəyişməz.
    """
    if body.a_id == body.b_id:
        raise HTTPException(400, "məhsul özü ilə müqayisə olunmur")
    if pair_state(body.a_id, body.b_id) is None:
        raise HTTPException(404, "məhsul tapılmadı")
    decide(body.a_id, body.b_id, body.same)
    state = pair_state(body.a_id, body.b_id)
    return {"applied": state["same_group"] == body.same, "counts": state["counts"]}
