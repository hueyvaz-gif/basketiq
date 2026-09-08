// Bütün səhifələrin PAYLAŞDIĞI kiçik funksiyalar: qaçırma, qiymət yazılışı,
// ikon, market nişanı.
//
// NİYƏ AYRICA FAYL OLDU?
// Əvvəl bunlar `app.js`-in başında idi. `app.js` isə yükləndiyi anda
// `$("#dropzone").addEventListener(...)` çağırır — yəni onu məhsul
// səhifəsinə qoşsaq, orada `#dropzone` olmadığı üçün fayl İLK SƏTİRDƏN
// qırılardı və səhifənin heç bir hissəsi işləməzdi.
//
// İki çıxış yolu vardı: funksiyaları məhsul səhifəsində TƏKRAR yazmaq, ya da
// paylaşılan hissəni ayırmaq. Təkrar yazmaq kateqoriya ikonları xəritəsini
// İKİ nüsxəyə bölərdi — `models.py`-yə yeni kateqoriya əlavə olunanda biri
// yenilənib digəri unudulardı və heç bir yerdə xəta çıxmazdı (bax
// `tests/test_ui_contract.py`). Ona görə ayrı fayl.
//
// Modul (`type="module"`) DEYİL: layihədə build addımı yoxdur və qalan
// skriptlər də qlobal sahədə işləyir. Bir faylı modul etsək, ondan çıxan
// adları qalan fayllar görməzdi.

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

const money = (v) => (v == null ? "—" : Number(v).toFixed(2));

// İkonlar HTML-in başındakı <symbol> kitabxanasından gəlir.
// Rəng SVG-də deyil, CSS-də təyin olunur (`currentColor`).
const icon = (name) =>
  `<svg aria-hidden="true"><use href="#icon-${name}"></use></svg>`;

// Məhsul kateqoriyası -> ikon.
//
// Açarlar `app/models.py`-dəki CATEGORIES siyahısından hərfbəhərf götürülüb -
// backend məhz o dəyərləri qaytarır. Siyahıya yeni kateqoriya əlavə olunsa,
// burada da bir sətir lazımdır; o vaxta qədər `digər` ikonu düşür.
//
// Niyə şəkil deyil, ikon? Layihədə məhsul şəkli YOXDUR - nə DB-də sütun var,
// nə də kataloqdan çıxarılır. Uydurma şəkil qoymaq isə istifadəçini yanıldardı.
const CATEGORY_ICON = {
  "süd məhsulları": "cat-dairy",
  "çörək və taxıl": "cat-bread",
  "ət və balıq": "cat-meat",
  "meyvə-tərəvəz": "cat-produce",
  "içkilər": "cat-drinks",
  "yağ və souslar": "cat-oil",
  "şirniyyat": "cat-sweets",
  "quru ərzaq": "cat-dry",
  "təmizlik və gigiyena": "cat-clean",
  "digər": "package",
};

const categoryIcon = (category) => CATEGORY_ICON[category] || "package";

/**
 * Marketin görsəl nişanı: RƏNGLİ DAİRƏ + adın ilk hərfi.
 *
 * Hərf marketi, rəng isə sabit kimliyi bildirir (rəngi `store-colors.js`
 * ADDAN hesablayır, sıradan yox — market siyahısı çeşidlənəndə rəng
 * dəyişməməlidir).
 *
 * Real loqo ÇƏKİLMİR: `stores` cədvəlində loqo yoxdur, uydurmuruq.
 */
const storeInitial = (name) => (String(name).trim()[0] || "?").toLocaleUpperCase("az");

const storeAvatar = (name, cls = "") =>
  `<span class="avatar is-store ${cls}" style="color:${StoreColors.cssVar(name)}" ` +
  `aria-hidden="true">${esc(storeInitial(name))}</span>`;

/** Market = nişan + ad. */
const storeChip = (name, best = false) =>
  `<span class="store-chip${best ? " is-best" : ""}">` +
  storeAvatar(name, "is-xs") +
  `${esc(name)}</span>`;

/** Valyuta işarəsi rəqəmdən nazik göstərilir - fokus ədədin üstündə qalsın. */
const price = (v) => `${money(v)}<span class="cur">₼</span>`;

function notice(el, kind, html) {
  el.innerHTML = `<div class="notice ${kind}">${html}</div>`;
}
