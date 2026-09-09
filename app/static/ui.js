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
 * MƏHSULUN LÖVHƏSİ: şəkil, yoxdursa KATEQORİYA lövhəsi.
 *
 * NİYƏ DƏYİŞDİ? Əvvəl şəkli olmayan hər məhsul eyni boz kubu (placeholder
 * SVG) alırdı. Bazada 188 məhsul var, şəkli isə 61-inin (≈32%) - yəni
 * səhifənin üçdə ikisi eyni boz kvadratdan ibarət idi və «yüklənməyib»
 * kimi oxunurdu.
 *
 * İndi şəkli olmayan məhsul öz kateqoriyasının İKONUNU və RƏNGİNİ alır:
 * süd mavi, ət çəhrayı, təmizlik firuzəyi. Uydurma foto qoyulmur - ikon
 * heç nə iddia etmir, sadəcə növü bildirir.
 *
 * RƏNG TƏK SİQNAL DEYİL: hər kateqoriyanın həm rəngi, həm də ayrı ikonu
 * var, yəni rəngi ayırd etməyən istifadəçi də formanı görür.
 */
function productThumb(item, cls = "") {
  const sinif = ["thumb", cls].filter(Boolean).join(" ");
  // `cat-dairy` -> `is-cat-dairy`; tanınmayan kateqoriya `package` ikonunu
  // alır və neytral boz lövhədə qalır.
  const ikon = categoryIcon(item.category);
  // Kateqoriya lövhəsi ŞƏKİLLİ məhsulda da qutuya yazılır (`data-cat`):
  // fayl tapılmasa ehtiyat qatı onu oradan oxuyur - məhsulun kateqoriyası
  // o anda əlçatan olmur.
  if (item.image) {
    return (
      `<span class="${sinif}" data-cat="${esc(ikon)}">` +
      `<img src="${esc(item.image)}" alt="" loading="lazy"></span>`
    );
  }
  return (
    `<span class="${sinif} is-cat ${categoryTone(ikon)}" data-cat="${esc(ikon)}">` +
    `${icon(ikon)}</span>`
  );
}

const categoryTone = (ikon) => (ikon === "package" ? "is-cat-other" : `is-${ikon}`);

/**
 * ŞƏKİL FAYLI YOXDURSA — kateqoriya lövhəsinə keçir.
 *
 * REAL HAL: `app/static/images/products/` qovluğu `.gitignore`-dadır və
 * `tools/build_images.py` ilə bərpa olunur. Yəni təzə klonda BAZADA şəkil
 * yolu var, DİSKDƏ isə fayl yoxdur. Ehtiyat olmasa, istifadəçi qırıq şəkil
 * nişanları görərdi - səhifə sınmış kimi.
 *
 * NİYƏ TƏK DİNLƏYİCİ, HƏR ŞƏKİLDƏ AYRI YOX?
 * `error` hadisəsi qabarmır (bubble), amma TUTMA (capture) mərhələsində
 * sənədə çatır. Bir dinləyici bütün səhifələri, hətta sonradan çəkilən
 * kartları da əhatə edir - hər renderdən sonra yenidən bağlamaq lazım gəlmir.
 */
document.addEventListener(
  "error",
  (e) => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    const thumb = img.closest(".thumb");
    if (!thumb || thumb.classList.contains("is-cat")) return;

    const ikon = thumb.dataset.cat || "package";
    thumb.classList.add("is-cat", categoryTone(ikon));
    thumb.innerHTML = icon(ikon);
  },
  true
);

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
