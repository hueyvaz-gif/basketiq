"""
Pydantic sxemləri.

DİQQƏT — LAYİHƏNİN ƏN VACİB QƏRARLARINDAN BİRİ:
LLM-dən qiymət SORUŞMURUQ. Qiyməti regex çıxarır (ingestion/cleaner.py).

Niyə? Çünki modelin uydura biləcəyi ən təhlükəli şey rəqəmdir - səhv qiymət
bütün müqayisəni korlayır və istifadəçi bunu görə bilmir. Regex isə ya tapır,
ya tapmır; uydurmur.

Beləliklə LLM-in işi yalnız MƏTNİ başa düşməkdir: ad, brend, ölçü, kateqoriya.
Bu, həm hallucination riskini sıfıra endirir, həm də cavabı qısaldıb GPU-suz
maşında emalı sürətləndirir.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

SizeUnit = Literal["kg", "g", "l", "ml", "pcs"]

CATEGORIES = [
    "süd məhsulları",
    "çörək və taxıl",
    "ət və balıq",
    "meyvə-tərəvəz",
    "içkilər",
    "yağ və souslar",
    "şirniyyat",
    "quru ərzaq",
    "təmizlik və gigiyena",
    "digər",
]

Category = Literal[
    "süd məhsulları",
    "çörək və taxıl",
    "ət və balıq",
    "meyvə-tərəvəz",
    "içkilər",
    "yağ və souslar",
    "şirniyyat",
    "quru ərzaq",
    "təmizlik və gigiyena",
    "digər",
]


class ProductAttributes(BaseModel):
    """LLM-in bir kataloq sətrindən çıxardığı atributlar. Qiymət YOXDUR."""

    name: str = Field(description="Məhsulun adı, brend və ölçü olmadan. Məsələn: 'süd'")
    brand: Optional[str] = Field(default=None, description="Brend adı, yoxdursa null")
    size_value: Optional[float] = Field(default=None, description="Ölçünün rəqəmi, məsələn 1.5")
    size_unit: Optional[SizeUnit] = Field(default=None, description="kg, g, l, ml və ya pcs")
    category: Category = Field(default="digər", description="Məhsulun kateqoriyası")

    @field_validator("name", "brand")
    @classmethod
    def _clean_text(cls, v):
        if v is None:
            return None
        v = " ".join(str(v).split()).strip(" .,-")
        return v or None

    @field_validator("size_value")
    @classmethod
    def _sane_size(cls, v):
        if v is None:
            return None
        if not (0 < v <= 10000):
            raise ValueError(f"ölçü ağlabatan deyil: {v}")
        return v


class ExtractedProduct(BaseModel):
    """Yekun məhsul: LLM atributları + regex qiyməti + hesablanmış sahələr."""

    name: str
    brand: Optional[str] = None
    size_value: Optional[float] = None
    size_unit: Optional[SizeUnit] = None
    category: str = "digər"

    price: float
    old_price: Optional[float] = None
    unit_price: Optional[float] = None       # 1 kq / 1 L qiyməti
    base_unit: Optional[str] = None          # 'kg' | 'l' | 'pcs'

    canonical_key: str
    raw_line: str

    @property
    def display_size(self) -> str:
        if self.size_value is None or self.size_unit is None:
            return ""
        value = int(self.size_value) if self.size_value == int(self.size_value) else self.size_value
        return f"{value} {self.size_unit}"


# --- API cavab modelləri ---


class HealthResponse(BaseModel):
    status: str
    env: str
    database: dict
    llm: dict
