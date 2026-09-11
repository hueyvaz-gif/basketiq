"""
Məhsul uyğunlaşdırma (product matching).

PROBLEM: Bravo "Süd Milla 1 L" yazır, Araz "Milla süd 1000 ml" yazır.
İnsan üçün bu eyni məhsuldur, kompüter üçün iki fərqli sətir.

HİBRİD HƏLL - üç pillə, ucuzdan bahaya:

  1) canonical_key      (pulsuz, ani)     -> hallarin ~90%-i
     "Milla süd 1000 ml" və "Süd Milla 1 L" hər ikisi -> milla|sud|1l
     Bunlar DB-yə eyni sətir kimi düşür, ayrıca iş görmək lazım deyil.

  2) oxşarlıq süzgəci   (pulsuz, ani)     -> namizədləri seçir
     Ortaq söz nisbəti hesablanır (şəkilçilər nəzərə alınmadan).
     Ölçüləri ziddiyyətli olan cütlər atılır.
     Ümumiyyətlə oxşamayan cütlər LLM-ə heç göndərilmir.

  3) LLM qərarı         (bahalı, ~2 san)  -> yalnız şübhəli qalanlar
     "günəbaxan yağı" və "günəbaxan yağ" eynidirmi? Bunu yalnız dil bilən
     model deyə bilər.

NİYƏ BELƏ? Hər cütü LLM-ə göndərmək 16 məhsul üçün 120 çağırış = 20 dəqiqə
deməkdir. Süzgəcdən sonra adətən 3-5 çağırış qalır = 10 saniyə.
"""

import json
from dataclasses import dataclass

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field

from ai import cache
from ai.blocking import candidate_pairs
from ai.llm import active_model_name, get_llm, message_text
from ai.prompts import MATCH_PROMPT, MATCH_PROMPT_VERSION
from app.config import settings
from app.db import PRICE_ROWS_CTE, db_cursor, get_connection
from ingestion.normalize import display_label, fat_percent, match_key

# Bu həddən aşağı oxşarlıq -> LLM-ə göndərmirik (açıq-aşkar fərqlidir)
MIN_SIMILARITY = 0.34


class MatchDecision(BaseModel):
    same: bool = Field(description="İki məhsul eynidirmi")


@dataclass
class Candidate:
    a_id: int
    b_id: int
    a_text: str
    b_text: str
    similarity: float


# ------------------------------------------------------------- ucuz pillə (1-2)


def key_parts(canonical_key: str) -> tuple[set[str], str]:
    """
    'milla|sud|1l' -> ({'milla','sud'}, '1l')

    Ölçü hissəsi ayrıca qaytarılır, çünki 1 L və 2 L EYNİ məhsul deyil -
    onları birləşdirsək səbət müqayisəsi tamamilə yanlış olar.
    """
    parts = [p for p in canonical_key.split("|") if p]
    if not parts:
        return set(), ""

    last = parts[-1]
    # Ölçü tokeni rəqəmlə başlayır: '1l', '0.5kg', '10pcs'
    if last and last[0].isdigit():
        return set(parts[:-1]), last
    return set(parts), ""


MIN_PREFIX = 3


def tokens_match(a: str, b: str) -> bool:
    """
    İki sözün eyni kök olub-olmadığını yoxlayır.

    NİYƏ SADƏ BƏRABƏRLİK KİFAYƏT ETMİR:
    Azərbaycan dili aqlütinativdir - sözlərə şəkilçi qoşulur:
        düyü   -> düyüsü        makaron -> makaronu
        yumurta -> yumurtası    yağ     -> yağı
    Kataloqlarda hər market fərqli formada yazır. Dəqiq bərabərlik axtarsaq,
    eyni məhsulları qaçırarıq.

    Ona görə biri digərinin PREFİKSİDİRSƏ eyni sayırıq.
    MIN_PREFIX=3 vacibdir: "su" və "süd" qarışmasın deyə.
    """
    if a == b:
        return True
    if min(len(a), len(b)) < MIN_PREFIX:
        return False
    return a.startswith(b) or b.startswith(a)


def similarity(key_a: str, key_b: str) -> float:
    """
    Oxşarlıq: uyğunlaşan sözlərin nisbəti (şəkilçilər nəzərə alınmadan).

    0.0 = ortaq heç nə yoxdur,  1.0 = bütün sözlər uyğunlaşır.
    """
    words_a, _ = key_parts(key_a)
    words_b, _ = key_parts(key_b)
    if not words_a or not words_b:
        return 0.0

    matched_a = sum(1 for a in words_a if any(tokens_match(a, b) for b in words_b))
    matched_b = sum(1 for b in words_b if any(tokens_match(b, a) for a in words_a))
    return (matched_a + matched_b) / (len(words_a) + len(words_b))


def product_text(product: dict) -> str:
    """LLM-ə göstəriləcək qısa təsvir."""
    parts = [display_label(product.get("name") or "", product.get("brand"))]
    size_value, size_unit = product.get("size_value"), product.get("size_unit")
    if size_value and size_unit:
        value = int(size_value) if float(size_value).is_integer() else size_value
        parts.append(f"{value} {size_unit}")
    return " ".join(p for p in parts if p).strip()


def find_candidates(products: list[dict], min_similarity: float = MIN_SIMILARITY) -> list[Candidate]:
    """
    LLM-ə göndərməyə dəyən cütləri seçir.

    HANSI CÜTLƏRİN ümumiyyətlə müqayisə olunduğunu bloklama həll edir
    (`ai/blocking.py`): eyni brend bloku, fərqli market. Hər cütü hər cütlə
    müqayisə etmək 13 min məhsulda ~93 milyon cüt demək idi.

    Blok daxilində ucuz şərtlər:
      - ölçüləri ziddiyyət təşkil etməsin
      - yağlılıq faizləri ziddiyyət təşkil etməsin (2.5% ≠ 3.2%)
      - artıq eyni qrupda olmasınlar
      - oxşarlıq həddi keçsin

    Açar `match_key`-dir (ölçü addan da oxunur); o yoxdursa canonical_key.
    """
    candidates: list[Candidate] = []

    for i, j in candidate_pairs(products):
        a, b = products[i], products[j]
        key_a = a.get("match_key") or a["canonical_key"]
        key_b = b.get("match_key") or b["canonical_key"]
        _, size_a = key_parts(key_a)
        _, size_b = key_parts(key_b)

        # Hər ikisində ölçü bilinirsə və fərqlidirsə -> fərqli məhsuldur.
        # Amma birində ölçü ümumiyyətlə tanınmayıbsa (OCR/LLM səhvi), qərarı
        # LLM-ə buraxırıq - əks halda düzgün uyğunluğu qaçırardıq.
        if size_a and size_b and size_a != size_b:
            continue
        # Yağlılıq da eyni qaydadır: yalnız HƏR İKİSİNDƏ yazılıbsa müqayisə olunur.
        fat_a, fat_b = fat_percent(a.get("name")), fat_percent(b.get("name"))
        if fat_a is not None and fat_b is not None and fat_a != fat_b:
            continue
        if a.get("group_key") and a["group_key"] == b.get("group_key"):
            continue

        score = similarity(key_a, key_b)
        if score < min_similarity:
            continue

        candidates.append(
            Candidate(
                a_id=a["id"],
                b_id=b["id"],
                a_text=product_text(a),
                b_text=product_text(b),
                similarity=round(score, 3),
            )
        )

    # Ən oxşarlar əvvəl yoxlansın - limit varsa ən dəyərliləri işlədək
    candidates.sort(key=lambda c: -c.similarity)
    return candidates


# ------------------------------------------------------------- bahalı pillə (3)


def _expand_match(message: BaseMessage) -> str:
    """{"s":1} -> {"same": true}"""
    data = json.loads(message_text(message))
    value = data.get("s", data.get("same", 0))
    if isinstance(value, str):
        value = value.strip().lower() in {"1", "true", "bəli", "yes"}
    return json.dumps({"same": bool(value)})


def build_match_chain():
    """prompt | model | qısa cavabın açılması | parser"""
    parser = PydanticOutputParser(pydantic_object=MatchDecision)
    chain = MATCH_PROMPT | get_llm(json_mode=True, num_predict=32) | RunnableLambda(_expand_match) | parser
    return chain.with_retry(stop_after_attempt=2)


def verify_candidates(candidates: list[Candidate], use_cache: bool = True) -> tuple[list[Candidate], dict]:
    """LLM ilə təsdiqlənmiş cütləri qaytarır."""
    stats = {"checked": len(candidates), "from_cache": 0, "from_llm": 0, "failed": 0, "confirmed": 0}
    if not candidates:
        return [], stats

    keys = [
        cache.cache_key(
            active_model_name(),
            MATCH_PROMPT_VERSION,
            # Sıradan asılı olmasın: (A,B) və (B,A) eyni keş açarı versin
            "||".join(sorted([c.a_text.lower(), c.b_text.lower()])),
        )
        for c in candidates
    ]

    decisions: list[bool | None] = [None] * len(candidates)
    pending: list[int] = []

    for i, key in enumerate(keys):
        cached = cache.get(key) if use_cache else None
        if cached is None:
            pending.append(i)
        else:
            decisions[i] = bool(cached.get("same"))
            stats["from_cache"] += 1

    if pending:
        chain = build_match_chain()
        inputs = [
            {"product_a": candidates[i].a_text, "product_b": candidates[i].b_text}
            for i in pending
        ]
        outputs = chain.batch(
            inputs,
            config={"max_concurrency": settings.llm_max_concurrency},
            return_exceptions=True,
        )
        for idx, output in zip(pending, outputs):
            if isinstance(output, Exception):
                stats["failed"] += 1
                continue
            decisions[idx] = output.same
            stats["from_llm"] += 1
            if use_cache:
                cache.put(keys[idx], {"same": output.same})

    confirmed = [c for c, same in zip(candidates, decisions) if same]
    stats["confirmed"] = len(confirmed)
    return confirmed, stats


# ------------------------------------------------------------- qrupların yazılması


class UnionFind:
    """
    Birləşən qrupları idarə edir.

    Niyə lazımdır? A=B və B=C təsdiqlənsə, A=C də olmalıdır.
    Sadə "cüt-cüt yaz" yanaşması bunu qaçırar.
    """

    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a


def load_products() -> list[dict]:
    """
    Uyğunlaşdırma üçün məhsullar + hər birinin satıldığı marketlər.

    `stores` bloklama üçündür (`ai/blocking.py`): eyni marketin iki məhsulu
    heç vaxt eyni sayılmır. Qiyməti olmayan məhsulda boş çoxluqdur.

    `match_key` NULL-dursa burada hesablanır: `_migrate` onu yalnız server
    başlanğıcında doldurur, yəni gün ərzində çəkilən yeni sətir açarsız
    qalardı və uyğunlaşdırma onu canonical_key ilə (ölçüsüz) müqayisə edərdi.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, canonical_key, match_key, name, brand, size_value, size_unit, group_key "
            "FROM products ORDER BY id"
        ).fetchall()
        stores: dict[int, set[int]] = {}
        for row in conn.execute(
            f"{PRICE_ROWS_CTE} SELECT DISTINCT product_id, store_id FROM price_rows"
        ):
            stores.setdefault(row["product_id"], set()).add(row["store_id"])
    finally:
        conn.close()

    products = []
    for row in rows:
        p = dict(row)
        p["stores"] = stores.get(p["id"], set())
        if not p["match_key"]:
            p["match_key"] = match_key(p["name"], p["brand"], p["size_value"], p["size_unit"])
        products.append(p)
    return products


def apply_groups(products: list[dict], confirmed: list[Candidate]) -> int:
    """
    Təsdiqlənmiş cütləri qruplara çevirir və DB-yə yazır.

    Qrupun adı - içindəki ən kiçik canonical_key. Beləliklə nəticə
    təkrar işlətmədən asılı olmur (deterministikdir).
    """
    if not confirmed:
        return 0

    union = UnionFind()
    by_id = {p["id"]: p for p in products}
    for candidate in confirmed:
        union.union(candidate.a_id, candidate.b_id)

    groups: dict[int, list[int]] = {}
    for product_id in list(union.parent):
        groups.setdefault(union.find(product_id), []).append(product_id)

    updated = 0
    with db_cursor() as cur:
        for members in groups.values():
            if len(members) < 2:
                continue
            group_key = min(by_id[m]["canonical_key"] for m in members)
            for member in members:
                cur.execute("UPDATE products SET group_key = ? WHERE id = ?", (group_key, member))
                updated += 1

    return updated


def run_matching(limit: int = 20, use_cache: bool = True) -> dict:
    """
    Bütün prosesi işə salır.

    limit: LLM-ə göndəriləcək maksimum cüt sayı. GPU-suz maşında hər cüt
    ~2 saniyədir, ona görə susmaya görə 20 ilə məhdudlaşdırılıb.
    """
    products = load_products()
    candidates = find_candidates(products)

    truncated = len(candidates) > limit
    selected = candidates[:limit]

    confirmed, stats = verify_candidates(selected, use_cache=use_cache)
    updated = apply_groups(products, confirmed)

    return {
        "products": len(products),
        "candidates_found": len(candidates),
        "candidates_checked": len(selected),
        "truncated": truncated,
        "llm": stats,
        "products_grouped": updated,
        "pairs": [
            {"a": c.a_text, "b": c.b_text, "similarity": c.similarity}
            for c in confirmed
        ],
        # Yoxlanılan, amma FƏRQLİ sayılan cütlər - şəffaflıq üçün
        "rejected": [
            {"a": c.a_text, "b": c.b_text, "similarity": c.similarity}
            for c in selected
            if c not in confirmed
        ],
    }


def load_groups() -> list[dict]:
    """Birdən çox məhsulu olan qruplar - UI-da göstərmək üçün."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT group_key, COUNT(*) AS members, "
            "       GROUP_CONCAT(COALESCE(brand,'') || ' ' || name, ' | ') AS names "
            "FROM products GROUP BY group_key HAVING COUNT(*) > 1 "
            "ORDER BY members DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
