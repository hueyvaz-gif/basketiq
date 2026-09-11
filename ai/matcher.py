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
from ai.blocking import candidate_pairs, known_brands, product_brand
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
            "SELECT id, canonical_key, match_key, name, brand, size_value, size_unit, "
            "group_key, barcode FROM products ORDER BY id"
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


# ------------------------------------------------------------- üç pillə (ADDIM 3)
#
# HƏDLƏR REAL BAZADA ÖLÇÜLÜB (2026-09-11, bloklamadan sonra 2 811 namizəd):
#   ≥0.90         37 cüt  -> brend və ölçü də eynidirsə AVTOMATİK
#   0.75-0.90    284 cüt  -> ŞÜBHƏLİ: LLM qərar verir, insan yoxlaya bilər
#   <0.75      2 490 cüt  -> atılır. Burada əsasən «ümumi ↔ konkret» cütlər
#                            var: «dondurma [Milla]» ⇄ «Milla Vanilli Dondurma»
#                            (0.57). Kataloq sətri hansı dondurma olduğunu
#                            demir — birləşdirmək səhv olardı.
AUTO_MIN_SIMILARITY = 0.90
LLM_MIN_SIMILARITY = 0.75


def _size_of(product: dict) -> str:
    """'milla|sud|1l' -> '1l'.  Ölçü bilinmirsə boş sətir."""
    return key_parts(product.get("match_key") or product["canonical_key"])[1]


def barcode_candidates(products: list[dict]) -> list[Candidate]:
    """
    1-ci pillə: eyni barkod FƏRQLİ marketlərdə = eyni məhsul (100% dəqiq).

    BU GÜN BAZADA BARKOD YOXDUR (0 dolu sətir): nə OCR kataloqu, nə Wolt
    kartı onu vermir. Pillə yenə də burada durur — mənbə barkod verməyə
    başlasa, heç bir LLM çağırışı olmadan işə düşəcək.
    """
    by_code: dict[str, list[dict]] = {}
    for p in products:
        code = (p.get("barcode") or "").strip()
        if code:
            by_code.setdefault(code, []).append(p)

    found: list[Candidate] = []
    for members in by_code.values():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                # Eyni marketdə eyni barkod iki sətirdirsə, bu, datanın öz
                # təkrarıdır - uyğunlaşdırmanın işi deyil.
                if a.get("stores") and b.get("stores") and a["stores"] & b["stores"]:
                    continue
                found.append(
                    Candidate(
                        a_id=a["id"],
                        b_id=b["id"],
                        a_text=product_text(a),
                        b_text=product_text(b),
                        similarity=1.0,
                    )
                )
    return found


def classify_candidates(
    products: list[dict], candidates: list[Candidate]
) -> tuple[list[Candidate], list[Candidate]]:
    """
    2-ci pillə: namizədləri AVTOMATİK və ŞÜBHƏLİ-yə ayırır.

    AVTOMATİK = bal ≥0.90 VƏ brend hər iki tərəfdə bilinir və eynidir VƏ
    ölçü hər iki tərəfdə bilinir və eynidir.

    NİYƏ YALNIZ BAL KİFAYƏT DEYİL? Real bazada «President kərə yağı»
    (kataloq, ölçüsüz) həm «...200qr», həm «...1kq» ilə 1.00 verir. Bal
    eynidir, amma kataloq sətrinin hansı olduğunu yalnız LLM (və ya insan)
    deyə bilər. Brend üçün də eyni: brendsiz «sirab su» brendli məhsulla
    birləşməzdən əvvəl yoxlanılmalıdır.
    """
    brands = known_brands(products)
    by_id = {p["id"]: p for p in products}
    auto: list[Candidate] = []
    suspicious: list[Candidate] = []

    for c in candidates:
        if c.similarity < LLM_MIN_SIMILARITY:
            continue
        a, b = by_id[c.a_id], by_id[c.b_id]
        brand_a, brand_b = product_brand(a, brands), product_brand(b, brands)
        size_a, size_b = _size_of(a), _size_of(b)
        certain = bool(brand_a) and brand_a == brand_b and bool(size_a) and size_a == size_b
        if c.similarity >= AUTO_MIN_SIMILARITY and certain:
            auto.append(c)
        else:
            suspicious.append(c)

    return auto, suspicious


class GuardedUnion(UnionFind):
    """
    UnionFind + iki qadağa. Birləşmə qrupda bunlardan birini yaradırsa, RƏDD edilir:
      - iki fərqli ölçü           (200 q kərə yağı ≠ 1 kq kərə yağı)
      - eyni marketin iki məhsulu (market bir məhsulu rəfində iki dəfə satmır)

    NİYƏ ADİ UnionFind TƏHLÜKƏLİDİR? Keçişli birləşmə: A=B və A=C təsdiqlənsə,
    B=C avtomatik olur. Real bazada ölçüsüz «President kərə yağı» həm 200 q,
    həm 1 kq ilə 1.00 verir — adi UnionFind ikisini BİR məhsula çevirərdi və
    səbət 1 kq-ın qiymətini 200 q ilə müqayisə edərdi.

    Əvvəlki qaçışların qrupları (eyni group_key) TOXUM kimi əvvəlcədən
    birləşdirilir ki, yeni qaçış onları sındırmasın.
    """

    def __init__(
        self,
        products: list[dict],
        forbidden: set[tuple[int, int]] | None = None,
        seed: bool = True,
    ) -> None:
        """
        forbidden: «fərqlidir» qərarları (insan və ya LLM) - bu iki məhsul
            HEÇ VAXT bir qrupda ola bilməz, üçüncü məhsul vasitəsilə də.
        seed: mövcud group_key-ləri toxum kimi götür. `rebuild_groups` bunu
            SÖNDÜRÜR: orada qruplar yalnız qərarlardan qurulur.
        """
        super().__init__()
        self.stores: dict[int, set] = {}
        self.sizes: dict[int, set[str]] = {}
        self.members: dict[int, set[int]] = {}
        self.forbidden: dict[int, set[int]] = {}
        for a, b in forbidden or ():
            self.forbidden.setdefault(a, set()).add(b)
            self.forbidden.setdefault(b, set()).add(a)
        by_group: dict[str, list[int]] = {}
        for p in products:
            self.find(p["id"])
            self.stores[p["id"]] = set(p.get("stores") or ())
            size = _size_of(p)
            self.sizes[p["id"]] = {size} if size else set()
            self.members[p["id"]] = {p["id"]}
            if seed and p.get("group_key"):
                by_group.setdefault(p["group_key"], []).append(p["id"])
        for members in by_group.values():
            for other in members[1:]:
                self._merge(self.find(members[0]), self.find(other))

    def _merge(self, root_a: int, root_b: int) -> None:
        if root_a == root_b:
            return
        self.parent[root_b] = root_a
        self.stores[root_a] |= self.stores.pop(root_b)
        self.sizes[root_a] |= self.sizes.pop(root_b)
        self.members[root_a] |= self.members.pop(root_b)

    def _forbidden_between(self, root_a: int, root_b: int) -> bool:
        """İki qrup arasında «fərqlidir» qərarı olan cüt varmı?"""
        small, large = sorted((root_a, root_b), key=lambda r: len(self.members[r]))
        others = self.members[large]
        return any(self.forbidden.get(m, set()) & others for m in self.members[small])

    def union(self, a: int, b: int) -> bool:  # type: ignore[override]
        """Birləşdirildisə (və ya onsuz da birdirsə) True, qadağa varsa False."""
        root_a, root_b = self.find(a), self.find(b)
        if root_a == root_b:
            return True
        if self.stores[root_a] & self.stores[root_b]:
            return False
        if len(self.sizes[root_a] | self.sizes[root_b]) > 1:
            return False
        if self._forbidden_between(root_a, root_b):
            return False
        self._merge(root_a, root_b)
        return True


def apply_groups(
    products: list[dict],
    confirmed: list[Candidate],
    dry_run: bool = False,
    forbidden: set[tuple[int, int]] | None = None,
    rebuild: bool = False,
    ordered: bool = False,
) -> dict:
    """
    Təsdiqlənmiş cütləri qruplara çevirir və DB-yə yazır.

    Cütlər BALA GÖRƏ azalan sırada birləşdirilir (`ordered=True` olsa -
    çağıranın sırası ilə): iki cüt ziddiyyət yaradırsa (bax `GuardedUnion`),
    daha etibarlı olan qalib gəlir, digəri `refused` siyahısına düşür —
    itmir, göstərilir.

    rebuild=True: qruplar YALNIZ bu cütlərdən qurulur (mövcud group_key
    toxum deyil) və heç bir qrupa düşməyən məhsul öz canonical_key-inə
    qayıdır. `rebuild_groups` belə çağırır — qərar silinəndə qrup da dağılsın.

    Qrupun adı - içindəki ən kiçik canonical_key. Beləliklə nəticə
    təkrar işlətmədən asılı olmur (deterministikdir).
    """
    union = GuardedUnion(products, forbidden=forbidden, seed=not rebuild)
    order = confirmed if ordered else sorted(confirmed, key=lambda c: -c.similarity)
    refused = [c for c in order if not union.union(c.a_id, c.b_id)]

    groups: dict[int, list[dict]] = {}
    for p in products:
        groups.setdefault(union.find(p["id"]), []).append(p)

    # Yalnız DƏYİŞƏN sətirlər yazılır: 13 min məhsulun hamısını hər qaçışda
    # yenidən yazmaq mənasızdır.
    changes: list[tuple[str, int]] = []
    for members in groups.values():
        if len(members) < 2:
            alone = members[0]
            if rebuild and alone.get("group_key") != alone["canonical_key"]:
                changes.append((alone["canonical_key"], alone["id"]))
            continue
        group_key = min(m["canonical_key"] for m in members)
        changes += [(group_key, m["id"]) for m in members if m.get("group_key") != group_key]

    if changes and not dry_run:
        with db_cursor() as cur:
            cur.executemany("UPDATE products SET group_key = ? WHERE id = ?", changes)

    return {"updated": len(changes), "refused": refused}


# ------------------------------------------------------------- qərar yaddaşı (ADDIM 4b)
#
# `match_decisions` cədvəli `group_key`-in MƏNBƏYİDİR (sxem və səbəbi:
# `app/db.py:_MATCH_DECISIONS_DDL`). Qruplar hər dəfə qərarlardan qurulur.

# Ziddiyyətdə kim qalib gəlir? Siyahıda ƏVVƏL gələn.
SOURCE_PRIORITY = {"human": 0, "barcode": 1, "auto": 2, "legacy": 3, "llm": 4}

_UPSERT = (
    "INSERT INTO match_decisions (a_id, b_id, decision, source, similarity, reason) "
    "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(a_id, b_id) DO UPDATE SET "
    "decision = excluded.decision, source = excluded.source, decided_at = datetime('now'), "
)
# Maşın: bal və səbəb yenilənir, amma İNSAN QƏRARININ üstünə yazılmır.
_UPSERT_MACHINE = _UPSERT + (
    "similarity = excluded.similarity, reason = excluded.reason "
    "WHERE match_decisions.source != 'human'"
)
# İnsan: hər şeyin üstündədir. Bal və səbəb (məs. «ölçü bilinmir») qalır -
# admin ekranı sonra da cütün niyə soruşulduğunu göstərə bilsin.
_UPSERT_HUMAN = _UPSERT + (
    "similarity = COALESCE(excluded.similarity, match_decisions.similarity), "
    "reason = COALESCE(excluded.reason, match_decisions.reason)"
)


def _pair_key(a_id: int, b_id: int) -> tuple[int, int]:
    """Cüt sırasızdır: (A,B) və (B,A) eyni açardır (cədvəldə `a_id < b_id`)."""
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def load_decisions() -> dict[tuple[int, int], dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT a_id, b_id, decision, source, similarity, reason, decided_at "
            "FROM match_decisions"
        ).fetchall()
    finally:
        conn.close()
    return {(r["a_id"], r["b_id"]): dict(r) for r in rows}


def record_decisions(rows: list[dict]) -> int:
    """MAŞIN qərarlarını yazır. `source='human'` sətrinə toxunmur."""
    if not rows:
        return 0
    params = []
    for r in rows:
        a, b = _pair_key(r["a_id"], r["b_id"])
        params.append((a, b, r["decision"], r["source"], r.get("similarity"), r.get("reason")))
    with db_cursor() as cur:
        cur.executemany(_UPSERT_MACHINE, params)
    return len(params)


def rebuild_groups(
    products: list[dict] | None = None, dry_run: bool = False, extra: list[dict] | None = None
) -> dict:
    """
    `group_key`-i BÜTÜN qərarlardan yenidən qurur.

    Sıra: insan > barkod > avtomatik > köhnə > LLM; eyni mənbədə bala görə.
    «different» qərarları qadağa kimi keçir - üçüncü məhsul vasitəsilə də.

    extra: hələ YAZILMAMIŞ qərarlar (dry_run üçün) - cədvəldəki mənzərənin
    üstünə qoyulur, amma insan qərarını əvəz etmir.
    """
    products = products if products is not None else load_products()
    by_id = {p["id"]: p for p in products}

    decisions = load_decisions()
    for r in extra or ():
        key = _pair_key(r["a_id"], r["b_id"])
        if decisions.get(key, {}).get("source") != "human":
            decisions[key] = {**r, "a_id": key[0], "b_id": key[1]}

    same = [
        d for d in decisions.values()
        if d["decision"] == "same" and d["a_id"] in by_id and d["b_id"] in by_id
    ]
    same.sort(key=lambda d: (SOURCE_PRIORITY.get(d["source"], 9), -(d.get("similarity") or 0)))
    forbidden = {key for key, d in decisions.items() if d["decision"] == "different"}

    confirmed = [
        Candidate(
            a_id=d["a_id"],
            b_id=d["b_id"],
            a_text=product_text(by_id[d["a_id"]]),
            b_text=product_text(by_id[d["b_id"]]),
            similarity=d.get("similarity") or 1.0,
        )
        for d in same
    ]
    return apply_groups(
        products, confirmed, dry_run=dry_run, forbidden=forbidden, rebuild=True, ordered=True
    )


def decide(a_id: int, b_id: int, same: bool) -> dict:
    """
    İNSAN qərarı (ADDIM 5, `/admin/matches`). Hər şeyin üstündədir və maşın
    qaçışları onu dəyişmir. Qruplar dərhal yenidən qurulur - istifadəçi
    düyməni basan kimi səbət müqayisəsi yeni vəziyyəti görür.
    """
    a, b = _pair_key(a_id, b_id)
    with db_cursor() as cur:
        cur.execute(_UPSERT_HUMAN, (a, b, "same" if same else "different", "human", None, None))
    return rebuild_groups()


def split_by_size(
    products: list[dict], suspicious: list[Candidate]
) -> tuple[list[Candidate], list[Candidate]]:
    """
    Şübhəliləri LLM-ə və İNSANA ayırır.

    Ölçü YALNIZ BİR tərəfdə bilinirsə, cüt birbaşa insana gedir. Səbəb:
    «Azərsüd ayran» (kataloq, ölçüsüz) Bravoda 290 ml, 200 ml və 1 l ilə
    eyni balı verir. LLM də ölçünü görmür və prompt «ümumi ↔ konkret»
    cütü EYNİ saydığı üçün üçünə də «bəli» deyərdi; GuardedUnion isə
    birincini birləşdirib qalanını rədd edərdi — yəni təsadüfi ölçü
    qalib gələrdi. Bunun üçün pul xərcləmək mənasızdır.

    Ölçü: real bazada 310 şübhəlidən 236-sı belədir. Kataloq sətrinin
    öz OCR mətnindən ölçü oxumaq da sınandı — 228 ölçüsüz məhsuldan
    cəmi 4-də tapıldı, dördü də yanlış idi.
    """
    by_id = {p["id"]: p for p in products}
    to_llm: list[Candidate] = []
    to_human: list[Candidate] = []
    for c in suspicious:
        known_a = bool(_size_of(by_id[c.a_id]))
        known_b = bool(_size_of(by_id[c.b_id]))
        (to_human if known_a != known_b else to_llm).append(c)
    return to_llm, to_human


def run_matching(limit: int = 20, use_cache: bool = True, dry_run: bool = False) -> dict:
    """
    Üç pilləni işə salır: barkod -> oxşarlıq -> LLM (yalnız şübhəlilər).

    limit: LLM-ə göndəriləcək maksimum ŞÜBHƏLİ cüt sayı. Avtomatik pillə
    limitə daxil deyil - o, pulsuzdur.
    dry_run: LLM çağırılmır və baza dəyişmir — nəyin birləşəcəyi və neçə
    cütün LLM-ə gedəcəyi əvvəlcədən görünür.
    """
    products = load_products()
    candidates = find_candidates(products, min_similarity=LLM_MIN_SIMILARITY)
    auto, suspicious = classify_candidates(products, candidates)
    to_llm, to_human = split_by_size(products, suspicious)
    by_barcode = barcode_candidates(products)

    # ARTIQ QƏRARI OLAN CÜT YENİDƏN SORUŞULMUR. Keş yalnız EYNİ MƏTNİ tutur
    # (ad bir hərf dəyişsə, yenidən soruşardı); qərar cədvəli isə cütün özünü.
    # İnsan qərarı olan cüt də LLM-ə getmir - cavabı onsuz da nəzərə alınmazdı.
    known = load_decisions()

    def answered(c: Candidate, sources: set[str]) -> bool:
        d = known.get(_pair_key(c.a_id, c.b_id))
        return bool(d) and d["source"] in sources and d["decision"] != "pending"

    selected = [c for c in to_llm if not answered(c, {"llm", "human"})][:limit]
    if dry_run:
        confirmed = []
        stats = {"checked": 0, "from_cache": 0, "from_llm": 0, "failed": 0, "confirmed": 0}
    else:
        confirmed, stats = verify_candidates(selected, use_cache=use_cache)

    def decision(c: Candidate, verdict: str, source: str, reason: str | None = None) -> dict:
        return {"a_id": c.a_id, "b_id": c.b_id, "decision": verdict, "source": source,
                "similarity": c.similarity, "reason": reason}

    new = [decision(c, "same", "barcode") for c in by_barcode]
    new += [decision(c, "same", "auto") for c in auto]
    new += [decision(c, "same", "llm") for c in confirmed]
    # «Fərqlidir» YALNIZ LLM HƏQİQƏTƏN cavab veribsə yazılır. Çağırışlardan biri
    # uğursuz olubsa (şəbəkə, limit), hansının olduğu buradan bilinmir - onda
    # heç biri «fərqli» yazılmır və növbəti qaçışda yenidən soruşulur. Xətanı
    # «fərqlidir» kimi yadda saxlamaq həmin cütü əbədi ayırardı.
    if not dry_run and not stats.get("failed"):
        new += [decision(c, "different", "llm") for c in selected if c not in confirmed]
    new += [
        decision(c, "pending", "auto", "ölçü bilinmir")
        for c in to_human
        if not answered(c, {"human"})
    ]

    if not dry_run:
        record_decisions(new)
    merged = by_barcode + auto + confirmed
    # Qruplar BÜTÜN qərarlardan qurulur (bu qaçışın + əvvəlkilərin + insanın).
    result = rebuild_groups(products, dry_run=dry_run, extra=new if dry_run else None)

    def pair(c: Candidate) -> dict:
        return {"a": c.a_text, "b": c.b_text, "similarity": c.similarity}

    return {
        "dry_run": dry_run,
        "products": len(products),
        "candidates_found": len(candidates),
        "levels": {
            "barcode": len(by_barcode),
            "auto": len(auto),
            "suspicious": len(suspicious),
            "llm": len(to_llm),
            "human": len(to_human),
        },
        "candidates_checked": len(selected),
        "truncated": len(to_llm) > limit,
        # Ölçü yalnız bir tərəfdə bilinir - LLM deyə bilməz, insan baxmalıdır (ADDIM 5)
        "needs_human": [dict(pair(c), reason="ölçü bilinmir") for c in to_human],
        "llm": stats,
        "products_grouped": result["updated"],
        "pairs": [pair(c) for c in merged if c not in result["refused"]],
        # Qadağaya düşən cütlər (iki ölçü və ya eyni market bir qrupda olardı)
        "refused": [pair(c) for c in result["refused"]],
        # Yoxlanılan, amma FƏRQLİ sayılan cütlər - şəffaflıq üçün
        "rejected": [] if dry_run else [pair(c) for c in selected if c not in confirmed],
        # dry_run-da: LLM-ə hansı cütlər GEDƏRDİ
        "to_llm": [pair(c) for c in selected] if dry_run else [],
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
