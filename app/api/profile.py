"""Profil endpoint-ləri və profilə uyğun tövsiyə."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.profile import Profile, get_profile, save_profile
from app.recommend import recommend

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileIn(BaseModel):
    """
    Gələn dəyərlərin tipi burada, HƏDDLƏRİ isə `app/profile.py`-dədir.

    Niyə ayrı? Endpoint yalnız bir giriş yoludur; MCP və skriptlər profili
    birbaşa `save_profile` ilə yazır. Hədd datanın yazıldığı yerdə olmalıdır
    ki, hansı yolla gəlməsindən asılı olmasın.
    """

    household_size: int = Field(default=1)
    weekly_budget: float | None = Field(default=None)
    max_stores: int = Field(default=1)
    min_split_saving: float = Field(default=1.0)
    prefer_unit_price: bool = Field(default=True)
    avoid: list[str] = Field(default_factory=list)


@router.get("")
def read_profile():
    profile = get_profile()
    return {
        **profile.as_dict(),
        "summary": profile.summary(),
        # Eyni təsvir açar+parametr şəklində: brauzer onu öz dilinə çevirir.
        "summary_keys": profile.summary_keys(),
    }


@router.put("")
def update_profile(data: ProfileIn):
    profile = save_profile(
        Profile(
            household_size=data.household_size,
            weekly_budget=data.weekly_budget,
            max_stores=data.max_stores,
            min_split_saving=data.min_split_saving,
            prefer_unit_price=data.prefer_unit_price,
            avoid=data.avoid,
        )
    )
    return {
        **profile.as_dict(),
        "summary": profile.summary(),
        # Eyni təsvir açar+parametr şəklində: brauzer onu öz dilinə çevirir.
        "summary_keys": profile.summary_keys(),
    }


@router.get("/recommend")
def profile_recommendation(basket_id: int = 1):
    """
    "Hansı market ucuzdur?" yox, "MƏNƏ nə etmək sərfəlidir?"

    Müqayisə rəqəmləri `compare()`-dən gəlir - burada yenidən hesablanmır.
    """
    from app.api.basket import compare

    data = compare(basket_id)
    return recommend(data).as_dict()
