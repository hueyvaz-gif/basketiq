"""
BLOKLAMA — hansı cütlər ümumiyyətlə müqayisə olunsun? (uyğunlaşdırma, ADDIM 2)

PROBLEM (ölçüldü, 2026-09-11): `find_candidates()` hər məhsulu hər məhsulla
müqayisə edirdi. 16 məhsulda bu 120 cüt idi. Bravonun mağaza qatı gələndən
sonra 13 654 məhsulda ~93 milyon cütdür — `/api/match/candidates` serveri
dəqiqələrlə kilidləyərdi.

HƏLL — iki qayda, ikisi də pulsuz və anidir:

  1) EYNİ BLOKDA OLMAYAN cüt müqayisə olunmur.
     Blok = brend (bilinirsə), yoxdursa sözün ilk 3 hərfi.

  2) EYNİ MARKETDƏ SATILAN iki məhsul HEÇ VAXT eyni deyil.
     Market bir məhsulu öz rəfində iki dəfə satmır: Bravoda «Milla Qatıq
     1.5%» və «Milla Qatıq 3.5%» ayrı sətirdirsə, deməli ayrı məhsuldur.
     Bu qayda həm də ən böyük qənaətdir: Bravonun 13 min məhsulu bir-biri
     ilə HEÇ müqayisə olunmur, yalnız digər marketlərin ~470 məhsulu ilə.

NİYƏ KATEQORİYA İLƏ YOX? Ölçüldü: Bravonun 50 kateqoriyası var (Wolt ağacı:
«Süd Məhsulları», «Spirtli İçkilər»), kataloqların isə 11 (LLM-in verdiyi:
«süd məhsulları», «içkilər»). Adlar üst-üstə düşmür — kateqoriya bloku əl
ilə xəritə tələb edərdi və xəritə köhnələn kimi uyğunluqlar səssizcə itərdi.

NİYƏ BREND VARSA YALNIZ BREND BLOKU? Fərqli brend = fərqli məhsul (bu,
LLM prompt-unun da qaydasıdır: «Milla ≠ President»). Brendli məhsulu söz
bloklarına da qoysaq, «süd» bloku yüzlərlə mənasız cüt verərdi.

NİYƏ 3 HƏRF? `matcher.tokens_match()` iki sözü biri digərinin prefiksidirsə
eyni sayır və ən azı 3 hərf tələb edir (MIN_PREFIX). Deməli uyğunlaşa bilən
iki sözün ilk 3 hərfi HƏMİŞƏ eynidir — 3 hərflik blok heç bir uyğunluğu
itirmir, sadəcə uyğunlaşa bilməyənləri atır.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from itertools import combinations
from itertools import product as cross

from ingestion.normalize import brand_from_name, slug_token

WORD_BLOCK_PREFIX = 3


def _words(key: str) -> list[str]:
    """'milla|sud|1l' -> ['milla', 'sud'].  Ölçü tokeni rəqəmlə başlayır."""
    return [part for part in key.split("|") if part and not part[0].isdigit()]


def known_brands(products: list[dict]) -> set[str]:
    """
    Brend lüğəti — brendi AYRICA yazılan məhsullardan (Araz/Rahat kataloqu).

    Bravo kartında brend sahəsi yoxdur; onun brendi bu lüğətlə addan tapılır
    (`normalize.brand_from_name`).
    """
    brands: set[str] = set()
    for p in products:
        slug = slug_token(p.get("brand") or "")
        if slug:
            brands.add(slug)
    return brands


def product_brand(product: dict, brands: set[str]) -> str | None:
    """Sahədəki brend üstündür; yoxdursa addan lüğətlə tapılır."""
    slug = slug_token(product.get("brand") or "")
    if slug:
        return slug
    return brand_from_name(product.get("name"), brands)


def blocking_keys(product: dict, brands: set[str]) -> set[str]:
    """Məhsulun düşdüyü bloklar: {'b:milla'} və ya {'w:sud', 'w:ayr'}."""
    brand = product_brand(product, brands)
    if brand:
        return {f"b:{brand}"}
    key = product.get("match_key") or product.get("canonical_key") or ""
    return {
        f"w:{word[:WORD_BLOCK_PREFIX]}"
        for word in _words(key)
        if len(word) >= WORD_BLOCK_PREFIX
    }


def candidate_pairs(products: list[dict]) -> Iterator[tuple[int, int]]:
    """
    Müqayisəyə dəyən cütlərin İNDEKSLƏRİ: (i, j), i < j, hər cüt bir dəfə.

    `stores` sahəsi (market id-ləri çoxluğu):
      - YOXDURSA — market bilinmir, cüt buraxılır (testlər, köhnə çağırışlar);
      - BOŞDURSA — məhsulun heç bir qiyməti yoxdur, müqayisəyə girmir:
        onu birləşdirmək səbətdə heç nə dəyişməz.
    """
    brands = known_brands(products)
    blocks: dict[str, list[int]] = defaultdict(list)
    for i, p in enumerate(products):
        if "stores" in p and not p["stores"]:
            continue
        for block in blocking_keys(p, brands):
            blocks[block].append(i)

    seen: set[tuple[int, int]] = set()
    for members in blocks.values():
        # Blok içində məhsullar market dəstinə görə qruplaşdırılır ki, EYNİ
        # marketin məhsulları cüt-cüt gəzilməsin: Bravonun «süd» blokunda
        # 1 000 məhsul olsa, bu 500 min boş yoxlama demək olardı.
        by_stores: dict[frozenset, list[int]] = defaultdict(list)
        for i in members:
            by_stores[frozenset(products[i].get("stores") or ())].append(i)

        signatures = list(by_stores)
        for x, left_sig in enumerate(signatures):
            for right_sig in signatures[x:]:
                if left_sig & right_sig:
                    continue  # ortaq market var -> fərqli məhsuldur
                left = by_stores[left_sig]
                if right_sig is left_sig:
                    pairs = combinations(left, 2)
                else:
                    pairs = cross(left, by_stores[right_sig])
                for i, j in pairs:
                    pair = (i, j) if i < j else (j, i)
                    if pair not in seen:
                        seen.add(pair)
                        yield pair
