"""
İstifadəçi profili — tövsiyəni ŞƏXSİLƏŞDİRƏN parametrlər.

NİYƏ LAZIMDIR?
"Ən ucuz market Araz-dır" cavabı hamı üçün eyni deyil:

  - Avtomobili olmayan adam üçün iki markete getmək 0.80 AZN qənaətə dəyməz.
  - 5 nəfərlik ailə üçün böyük qablaşdırma sərfəlidir, tək yaşayan üçün yox.
  - Həftəlik büdcəsi 60 AZN olan adama "səbət 78 AZN-dir" demək azdır -
    hansı məhsulun büdcəni yediyini də göstərmək lazımdır.

Profil bu fərqləri RƏQƏMƏ çevirir və tövsiyə məntiqi onlara görə dəyişir.
Yəni profil bəzək deyil - `app/recommend.py` içindəki qərarları idarə edir.

NİYƏ TƏK SƏTİR (id=1)?
Layihədə istifadəçi hesabı yoxdur (autentifikasiya 3-cü ayın mövzusu deyil).
Səbət də eyni prinsiplə tək sətirdir. Çox istifadəçi lazım olsa, cədvələ
user_id sütunu əlavə etmək kifayətdir - sxem buna hazırdır.
"""

from dataclasses import dataclass, field

from app.db import db_cursor, get_connection

PROFILE_ID = 1

# İkinci markete getmək vaxt və yol xərcidir. Bundan az qənaətə görə
# tövsiyə "iki markete get" deməməlidir - məsləhət praktik olmalıdır.
DEFAULT_MIN_SPLIT_SAVING = 1.0


@dataclass
class Profile:
    household_size: int = 1
    weekly_budget: float | None = None
    max_stores: int = 1
    min_split_saving: float = DEFAULT_MIN_SPLIT_SAVING
    prefer_unit_price: bool = True
    avoid: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "household_size": self.household_size,
            "weekly_budget": self.weekly_budget,
            "max_stores": self.max_stores,
            "min_split_saving": self.min_split_saving,
            "prefer_unit_price": self.prefer_unit_price,
            "avoid": self.avoid,
        }

    def summary(self) -> str:
        """Modelə və UI-a veriləcək qısa təsvir."""
        parts = [f"{self.household_size} nəfərlik ev"]
        if self.weekly_budget:
            parts.append(f"həftəlik büdcə {self.weekly_budget:.0f} AZN")
        parts.append(
            "yalnız bir markete gedir"
            if self.max_stores <= 1
            else f"ən çox {self.max_stores} markete gedə bilir"
        )
        if self.prefer_unit_price:
            parts.append("kq/litr qiymətinə baxır")
        if self.avoid:
            parts.append("istəmir: " + ", ".join(self.avoid))
        return "; ".join(parts)


def _parse_avoid(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [word.strip().lower() for word in raw.split(",") if word.strip()]


def get_profile() -> Profile:
    """Profili oxuyur. Sətir yoxdursa defolt dəyərlər qaytarılır."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM profile WHERE id = ?", (PROFILE_ID,)
        ).fetchone()
    except Exception:
        # Köhnə bazada cədvəl hələ yoxdur - defolt profil kifayətdir
        return Profile()
    finally:
        conn.close()

    if not row:
        return Profile()

    return Profile(
        household_size=row["household_size"],
        weekly_budget=row["weekly_budget"],
        max_stores=row["max_stores"],
        min_split_saving=row["min_split_saving"],
        prefer_unit_price=bool(row["prefer_unit_price"]),
        avoid=_parse_avoid(row["avoid"]),
    )


def save_profile(profile: Profile) -> Profile:
    """
    Profili yazır. Dəyərlər burada MƏHDUDLAŞDIRILIR.

    Niyə burada? Endpoint-də yoxlasaq, MCP və skript yolu ilə gələn dəyər
    yoxlanmadan keçərdi. Məhdudlaşdırma datanın girdiyi yerdə olmalıdır.
    """
    household = max(1, min(20, int(profile.household_size)))
    stores = max(1, min(5, int(profile.max_stores)))
    budget = None
    if profile.weekly_budget is not None:
        budget = max(0.0, float(profile.weekly_budget)) or None
    saving = max(0.0, float(profile.min_split_saving))
    avoid = [w.strip().lower() for w in profile.avoid if w.strip()][:20]

    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO profile (id, household_size, weekly_budget, max_stores, "
            "                     min_split_saving, prefer_unit_price, avoid) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "  household_size = excluded.household_size, "
            "  weekly_budget = excluded.weekly_budget, "
            "  max_stores = excluded.max_stores, "
            "  min_split_saving = excluded.min_split_saving, "
            "  prefer_unit_price = excluded.prefer_unit_price, "
            "  avoid = excluded.avoid",
            (
                PROFILE_ID,
                household,
                budget,
                stores,
                saving,
                1 if profile.prefer_unit_price else 0,
                ",".join(avoid),
            ),
        )

    return get_profile()
