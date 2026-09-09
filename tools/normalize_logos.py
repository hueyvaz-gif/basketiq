"""
C13 — market loqolarını VAHİD ölçü sisteminə gətirir.

PROBLEM ÖLÇÜLDÜ, uydurulmadı. Dörd loqonun mürəkkəb (ink) nisbəti:

    araz  3.23    bazar 5.83    bravo 3.99    rahat 2.91

Üstəlik iki fayl boşluq daşıyırdı: `rahat.png` 252x149 idi, mürəkkəbi isə
cəmi 154x53 - yəni qutunun ~78%-i boş ağ sahə. `bravo.png`-də də kənarlarda
boşluq vardı. `object-fit: contain` boşluğu da şəkil sayır, ona görə eyni
qutuda rahat kiçik, bazar isə nazik zolaq kimi görünürdü.

HƏLL: hər loqo əvvəlcə mürəkkəbinə qədər KƏSİLİR, sonra eyni nisbətli
(4:1) kətanın ORTASINA, EYNİ SAHƏ ilə yerləşdirilir.

NİYƏ «eyni hündürlük» yox, «eyni sahə»?
Eyni hündürlükdə bazar (5.83) rahatdan (2.91) 2 dəfə uzun olur; eyni
enlikdə isə əksi. Sahə normallaşdırması hər ikisini bölür: nə biri
zolağa dönür, nə digəri qutunu doldurur. Bu, loqo lokaplarında standart
üsuldur.

Nəticədə dörd faylın DA nisbəti eynidir (4:1), yəni CSS tərəfdə tək qutu
kifayət edir - `contain` hamısını eyni ölçüdə çəkir.
"""

import math
from pathlib import Path

import numpy as np
from PIL import Image

QAYNAQ = Path("app/static/images")
FAYLLAR = ["araz.png", "bazar.png", "bravo.png", "rahat.png"]

# Kətan: 4:1. Median nisbətə (3.6) yaxındır, yəni heç bir loqo həddindən
# artıq sıxılmır. Ölçü böyükdür ki, retina ekranda da kəskin qalsın.
KƏTAN_EN, KƏTAN_HÜND = 800, 200

# Mürəkkəbin hədəf SAHƏSİ. Aşağıdakı hədlərdən çıxıb: bazar enə görə,
# rahat isə hündürlüyə görə kətanı ilk aşan loqolardır - 85 000 hər ikisini
# kənarda ~%8 nəfəs payı ilə saxlayır.
HƏDƏF_SAHƏ = 85_000
MAKS_EN = int(KƏTAN_EN * 0.92)
MAKS_HÜND = int(KƏTAN_HÜND * 0.88)


def ink_bbox(im: Image.Image) -> tuple[int, int, int, int]:
    """Şəffaf VƏ ağ kənarları atır: yalnız görünən mürəkkəbin çərçivəsi."""
    arr = np.array(im.convert("RGBA"))
    görünən = (arr[:, :, :3] < 240).any(axis=2) & (arr[:, :, 3] > 10)
    ys, xs = görünən.nonzero()
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def normalize(path: Path) -> tuple[int, int]:
    im = Image.open(path).convert("RGBA")
    kəsik = im.crop(ink_bbox(im))
    en, hünd = kəsik.size
    nisbət = en / hünd

    yeni_hünd = min(MAKS_HÜND, math.sqrt(HƏDƏF_SAHƏ / nisbət))
    yeni_en = yeni_hünd * nisbət
    if yeni_en > MAKS_EN:  # enə görə də kəs
        yeni_en = MAKS_EN
        yeni_hünd = yeni_en / nisbət
    yeni_en, yeni_hünd = int(round(yeni_en)), int(round(yeni_hünd))

    kiçik = kəsik.resize((yeni_en, yeni_hünd), Image.LANCZOS)
    kətan = Image.new("RGBA", (KƏTAN_EN, KƏTAN_HÜND), (0, 0, 0, 0))
    kətan.paste(kiçik, ((KƏTAN_EN - yeni_en) // 2, (KƏTAN_HÜND - yeni_hünd) // 2), kiçik)
    kətan.save(path)
    return yeni_en, yeni_hünd


for ad in FAYLLAR:
    p = QAYNAQ / ad
    əvvəl = Image.open(p).size
    en, hünd = normalize(p)
    print(f"{ad:11} {əvvəl[0]}x{əvvəl[1]} -> kətan {KƏTAN_EN}x{KƏTAN_HÜND}, "
          f"mürəkkəb {en}x{hünd} (sahə {en * hünd:,})")
