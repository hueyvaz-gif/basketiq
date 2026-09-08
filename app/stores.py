"""
BasketIQ-in DÖRD marketi — yeganə reyestr.

NİYƏ AYRICA FAYL?
Layihənin `stores` cədvəli sərbəstdir: kataloq yükləyəndə market adı mətn
kimi yazılır, ona görə orada test marketləri və köhnə mənbələr də qalır
(`test-market`, `test-scrape-market`, `oba`). Trolley üslubundakı yeni
ekranlar — «bugünün endirimləri» və «harada al» — bu qarışıq siyahının
üstündə qurula bilməz: istifadəçiyə «Test Scrape Market»in qiymətini
göstərmək məlumat deyil, səs-küydür.

Ona görə MƏHSULUN öz market siyahısı burada, bir yerdə elan olunur. Bazadakı
sətir bu siyahıya düşmürsə, yeni ekranlarda GÖRÜNMÜR (admin panelində və
köhnə səbət müqayisəsində isə heç nə dəyişmir — onlar bazanın bütün
tarixçəsini göstərməkdə haqlıdır).

«MÖVCUD DEYİL» İLƏ «BOŞ»UN FƏRQİ.
Dörd marketin hamısının inteqrasiyası hazır deyil (ölçmələr: `logs/sources.md`).
Hazır olmayanı UI-dan tamamilə silmək yanlış olardı — istifadəçi «niyə cəmi
iki market var?» sualına cavab tapmazdı. Ona görə reyestr hər market üçün
`available` bayrağı verir: datası olan market qiymətlə, olmayan isə
«Tezliklə» yazısı ilə göstərilir. Heç bir halda boş sütun və ya xəta çıxmır.

ALİASLAR NİYƏ LAZIMDIR?
Eyni market bazaya müxtəlif adla düşə bilər: «Araz», «Araz Market»,
«araz-market». `app/db.py`-dəki `STORE_MERGES` bunları BİRLƏŞDİRİR, amma
birləşmə yalnız siyahıda yazılmış cütlər üçün işləyir. Reyestr isə oxuma
tərəfindən qoruyur: bazadakı slug aliaslardan birinə uyğun gəlirsə, həmin
sətir markete aid sayılır.
"""

from dataclasses import dataclass
from sqlite3 import Connection

from app.db import get_connection


@dataclass(frozen=True)
class Market:
    """Bir market. `short` cədvəl başlığı üçündür — «Araz Market» sütunu daraldır."""

    slug: str
    name: str
    short: str
    aliases: tuple[str, ...] = ()
    # Loqo faylının adı `app/static/images/` qovluğunda.
    #
    # NİYƏ SLUG-DAN AVTOMATİK DÜZƏLDİLMİR? Fayl adları ilə slug-lar üst-üstə
    # düşmür: «bazar-store» marketinin loqosu `bazar.png`-dir. Adı burada,
    # reyestrdə saxlamaq bu uyğunsuzluğu BİR yerdə cəmləyir; frontend-də
    # ayrıca xəritə saxlasaq, iki siyahı yaranardı.
    #
    # Fayl olmaya da bilər - o halda UI loqonun yerinə marketin adını yazır
    # (bax `stores.js`). Uydurma loqo çəkmirik.
    logo: str = ""

    @property
    def all_slugs(self) -> tuple[str, ...]:
        return (self.slug, *self.aliases)


# SIRA ƏHƏMİYYƏTLİDİR: «harada al» cədvəlində marketlər həmişə bu sıra ilə
# görünür. Qiymətə görə çeşidləmək cazibədar səslənir, amma o zaman sütunlar
# hər məhsulda yerini dəyişər və gözlə müqayisə mümkün olmaz.
MARKETS: tuple[Market, ...] = (
    Market(
        slug="araz",
        name="Araz Market",
        short="Araz",
        aliases=("araz-market",),
        logo="araz.png",
    ),
    Market(
        slug="bravo",
        name="Bravo Market",
        short="Bravo",
        aliases=("bravo-market",),
        logo="bravo.png",
    ),
    Market(
        slug="bazar-store",
        name="Bazar Store",
        short="Bazar",
        aliases=("bazarstore", "bazar"),
        logo="bazar.png",
    ),
    Market(
        slug="rahat",
        name="Rahat Market",
        short="Rahat",
        aliases=("rahat-market",),
        logo="rahat.png",
    ),
)

_BY_SLUG: dict[str, Market] = {
    alias: market for market in MARKETS for alias in market.all_slugs
}


def market_for(slug: str | None) -> Market | None:
    """Bazadakı slug -> reyestr marketi. Tanınmayan slug üçün None."""
    if not slug:
        return None
    return _BY_SLUG.get(slug.strip().lower())


def store_map(conn: Connection) -> dict[int, Market]:
    """
    `stores.id` -> Market. Yalnız reyestrdəki marketlər qayıdır.

    Bütün sorğular bu xəritədən keçir: SQL-də market adını təkrar yazmırıq,
    əvəzində `store_id IN (...)` şərtini buradan qururuq.
    """
    out: dict[int, Market] = {}
    for row in conn.execute("SELECT id, slug FROM stores"):
        market = market_for(row["slug"])
        if market is not None:
            out[row["id"]] = market
    return out


def store_filter(conn: Connection, column: str = "pr.store_id") -> tuple[str, tuple]:
    """
    SQL şərti + parametrləri: sorğunu YALNIZ dörd marketlə məhdudlaşdırır.

        clause, params = store_filter(conn)
        conn.execute(f"... WHERE p.group_key = ? AND {clause}", (key, *params))

    NİYƏ HAZIR ŞƏRT QAYTARIRIQ?
    Filtri hər sorğuda əl ilə yazmaq üç ayrı modulda üç ayrı həqiqət
    yaradardı: biri yenilənib digəri köhnə qalar, istifadəçi isə eyni
    səhifədə bir yerdə «Araz Market», başqa yerdə «OBA» görərdi. Məhz bu
    baş vermişdi - səbət cavabı OBA-nı tövsiyə edirdi, halbuki market
    şəbəkəsində belə market yox idi.

    BOŞ HAL QƏSDƏN «HEÇ NƏ» QAYTARIR. Reyestrdəki marketlərin heç birinin
    datası yoxdursa, şərt `0 = 1` olur - yəni cavab boş gəlir. `IN ()` SQL-də
    sintaksis səhvidir, «filtri ümumiyyətlə tətbiq etməmək» isə daha pisdir:
    o zaman istifadəçiyə bizim olmayan marketlərin qiymətləri göstərilərdi.
    """
    ids = sorted(store_map(conn))
    if not ids:
        return "0 = 1", ()
    return f"{column} IN ({','.join('?' * len(ids))})", tuple(ids)


def display_names(conn: Connection) -> dict[int, str]:
    """
    `stores.id` -> REYESTRDƏKİ ad.

    Bazadakı ad ilə reyestrdəki ad üst-üstə düşmür: kataloq yüklənəndə market
    «Araz» kimi yazılıb, məhsul isə «Araz Market» adlanır. İki ad iki problem
    yaradır: (1) istifadəçi eyni marketi iki cür görür, (2) market rəngi
    ADDAN hesablandığı üçün (`store-colors.js`) eyni market cədvəldə bir,
    qrafikdə başqa rəngə düşür.
    """
    return {store_id: market.name for store_id, market in store_map(conn).items()}


def market_status(conn: Connection | None = None) -> list[dict]:
    """
    Dörd marketin hamısı + hər birinin datası varmı.

    UI bunu belə oxuyur:
        available=True  -> qiymət göstər
        available=False -> «Tezliklə» yaz, sütun açma
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        counts: dict[str, int] = {}
        rows = conn.execute(
            "SELECT s.slug AS slug, COUNT(DISTINCT pr.product_id) AS products "
            "FROM stores s LEFT JOIN prices pr ON pr.store_id = s.id "
            "GROUP BY s.id"
        ).fetchall()
        for row in rows:
            market = market_for(row["slug"])
            if market is None:
                continue
            # Aliaslar birləşdirilir: «araz» və «araz-market» eyni marketdir.
            counts[market.slug] = counts.get(market.slug, 0) + (row["products"] or 0)

        return [
            {
                "slug": market.slug,
                "name": market.name,
                "short": market.short,
                # Ünvan, fayl adı deyil: fayl yoxdursa UI mətn nişanına keçir.
                "logo": f"/static/images/{market.logo}" if market.logo else None,
                "products": counts.get(market.slug, 0),
                "available": counts.get(market.slug, 0) > 0,
            }
            for market in MARKETS
        ]
    finally:
        if own:
            conn.close()
