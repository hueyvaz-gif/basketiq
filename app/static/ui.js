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

/**
 * Böyük tam ədədi minlik ayırıcı ilə yazır: 13139 -> «13 139».
 *
 * NİYƏ LAZIM OLDU: market kartında say ayırıcısız yazılırdı və «13139»
 * bir yığın rəqəm kimi görünürdü - göz onu bir baxışda oxuya bilmirdi,
 * yanındakı «379» ilə müqayisəsi isə çətinləşirdi.
 *
 * AYIRICI BOŞLUQDUR, vergül yox: Azərbaycan yazısında minlik ayırıcı
 * boşluqdur, vergül isə ONLUQ ayırıcıdır - «13,139» burada «on üç tam»
 * kimi oxuna bilərdi. ` ` qırılmayan boşluqdur ki, rəqəm sətir
 * sonunda ikiyə bölünməsin.
 *
 * `toLocaleString("az-AZ")` İŞLƏDİLMİR - brauzerdə ölçüldü: Chrome həmin
 * lokal üçün məhz VERGÜL qaytarır («13,139»). Yəni lokal adı düzgün olsa
 * da, nəticə yanlışdır. Format burada açıq yazılır: nəticə brauzerdən
 * asılı deyil.
 */
const count = (v) =>
  v == null
    ? "—"
    : String(Math.round(Number(v))).replace(/\B(?=(\d{3})+(?!\d))/g, " ");

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
// İkon nə vaxt düşür? M3-dən sonra məhsulun REAL fotosu varsa, foto
// göstərilir; ikon isə fotosu OLMAYAN məhsulun lövhəsidir. Ölçülmüş
// vəziyyət (2026-09-10): 188 məhsuldan 33-ünün fotosu var, 155-i ikondadır -
// yəni ikon istisna deyil, əsas haldır və elə də görünməlidir.
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
 * SVG) alırdı - səhifənin böyük hissəsi eyni boz kvadratdan ibarət idi və
 * «yüklənməyib» kimi oxunurdu. İndi belə məhsul öz kateqoriyasının
 * İKONUNU alır: uydurma foto qoyulmur - ikon heç nə iddia etmir, sadəcə
 * növü bildirir.
 *
 * KATEQORİYA RƏNGİ YOXDUR (M2.1): fərq üç neytral TON addımı ilə verilir.
 * Əvvəlki rəngli variant (süd mavi, ət çəhrayı) şəbəkəni mozaikaya
 * çevirirdi. Ayırd edici siqnal ikonun ÖZ FORMASIDIR - rəngdən asılı deyil.
 *
 * ŞƏKİLLİ HAL (M3): plitənin ölçüsü və yeri EYNİ QALIR, yalnız ikonun
 * yerini foto tutur. Fotolar endirilərkən ağ kvadrat kətana
 * normallaşdırılır (`app/services/product_images.py`), ona görə burada
 * nisbət düzəltməyə ehtiyac yoxdur.
 */
// KATALOQDAN KƏSİLMİŞ ŞƏKİLLƏRİN ÜNVAN PREFİKSİ.
//
// Bu şəkillər həftəlik kataloq SƏHİFƏSİNDƏN kəsilir (`ingestion/images.py`):
// nisbətləri müxtəlifdir, kənarlarında qonşu kartın parçası qalır, fonları
// isə kataloqun öz rəngidir. Kartlar yan-yana düzüləndə nəticə səliqəsiz
// görünür - biri ağ, biri sarı, biri yarımçıq.
//
// Emal zənciri SAXLANILIR (şəkillər admin üçün faydalıdır və gələcəkdə real
// məhsul fotosu mənbəyi tapılsa, qat hazırdır), amma İSTİFADƏÇİYƏ kəsik
// göstərilmir.
const CATALOG_CROP_PREFIX = "/static/images/products/";

const isCatalogCrop = (url) => String(url || "").startsWith(CATALOG_CROP_PREFIX);

function productThumb(item, cls = "") {
  const sinif = ["thumb", cls].filter(Boolean).join(" ");
  // `cat-dairy` -> `is-cat-dairy`; tanınmayan kateqoriya `package` ikonunu
  // alır və neytral boz lövhədə qalır.
  const ikon = categoryIcon(item.category);
  // Kateqoriya lövhəsi ŞƏKİLLİ məhsulda da qutuya yazılır (`data-cat`):
  // fayl tapılmasa ehtiyat qatı onu oradan oxuyur - məhsulun kateqoriyası
  // o anda əlçatan olmur.
  // REAL MƏHSUL FOTOSU varsa göstərilir; kataloq kəsiyi isə YOX (P5).
  //
  // İKİ PREFİKS BİR-BİRİNƏ ÇOX BƏNZƏYİR VƏ MƏNALARI TƏRSDİR:
  //   /static/images/products/  -> kataloq kəsiyi, GÖSTƏRİLMİR
  //   /static/product_images/   -> real foto,      GÖSTƏRİLİR
  // Birində sözlərin yeri dəyişsə, ya bütün fotolar səssizcə itər, ya da
  // bütün kəsiklər ekrana çıxar - hər ikisi səssiz sınmadır. Ona görə
  // `tests/test_ui_contract.py` hər iki prefiksin DƏYƏRİNİ kilidləyir.
  if (item.image && !isCatalogCrop(item.image)) {
    // ÖLÇÜ ATRIBUTLARI (M3): `width`/`height` olmasa, brauzer şəklin yerini
    // fayl gələnə qədər sıfır sayır və gələndə kart SIÇRAYIR. Atributlar
    // yalnız nisbəti bildirir - əsl ölçünü CSS verir (plitə sabitdir).
    //
    // `is-photo` sinfi plitənin fonunu verir: şəkil yüklənənə qədər yerində
    // hazır səth durur (skelet), yəni boş deşik olmur və şəkil gələndə fon
    // dəyişmir.
    const ölçü = item.image_w && item.image_h
      ? ` width="${item.image_w}" height="${item.image_h}"`
      : "";
    return (
      `<span class="${sinif} is-photo ${categoryTone(ikon)}" data-cat="${esc(ikon)}">` +
      `<img src="${esc(item.image)}" alt="" loading="lazy" decoding="async"${ölçü}></span>`
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
    // `is-photo` GÖTÜRÜLÜR: fotoya aid içəri boşluq və solğunlaşma ikona
    // aid deyil - ikon plitənin mərkəzində, tam ölçüdə dayanmalıdır.
    thumb.classList.remove("is-photo");
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

/**
 * SƏBƏTƏ ƏLAVƏ ET — bütün səhifələrin işlətdiyi tək funksiya.
 *
 * NİYƏ BURADA? Düymə üç yerdədir: axtarış kartı, məhsul səhifəsi və
 * məhsul səhifəsindəki «oxşar / eyni brend» kartları. Üç nüsxə olsaydı,
 * biri `qty` göndərməyi unudardı və səhv yalnız səbətdə görünərdi.
 *
 * DÜYMƏ ÖZ VƏZİYYƏTİNİ GÖSTƏRİR: klikdən sonra «Əlavə olundu» yazır və
 * sönür. Səhifə dəyişmir - istifadəçi axtarışa davam edə bilir. Üst
 * paneldəki nişan isə `basketiq:basket` hadisəsi ilə dərhal yenilənir.
 */
async function addToBasket(productId, btn) {
  const köhnə = btn ? btn.innerHTML : null;
  if (btn) btn.disabled = true;

  try {
    const res = await fetch("/api/basket/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: Number(productId), qty: 1 }),
    });
    if (!res.ok) throw new Error("http");

    if (btn) {
      btn.classList.add("is-added");
      btn.innerHTML = `${icon("check")}${esc(t("basket.added"))}`;
    }
    // Nişan və səbət səhifəsi bu hadisəni dinləyir.
    document.dispatchEvent(new CustomEvent("basketiq:basket"));
    return true;
  } catch {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = köhnə;
      btn.title = t("basket.addError");
    }
    return false;
  }
}

/** Səbətə əlavə düyməsi - kart və məhsul səhifəsi eyni işarələməni işlədir. */
const addButton = (productId, cls = "") =>
  `<button class="btn btn-secondary add-btn ${cls}" type="button" data-add="${productId}">` +
  `${icon("basket")}<span>${esc(t("basket.add"))}</span></button>`;

// Bütün səhifələrdə TƏK dinləyici: kartlar sonradan çəkilir, ona görə
// düymələrə tək-tək dinləyici bağlamaq mənasızdır.
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-add]");
  if (!btn) return;
  e.preventDefault();     // kart bir keçiddir - düymə onu açmamalıdır
  e.stopPropagation();
  addToBasket(btn.dataset.add, btn);
});


/* ============================================================================
   SİLMƏ TƏSDİQİ — iki addım

   NİYƏ `confirm()` DEYİL?
   Üç səbəb:
     1. `confirm()` səhifəni BLOKLAYIR - brauzer avtomatlaşdırması (bizim öz
        Selenium yoxlamalarımız da daxil) dialoq açılan kimi cavab verməyi
        dayandırır;
     2. onu üslublandırmaq mümkün deyil - Apple dizayn dilinin ortasında
        əməliyyat sisteminin boz qutusu açılır;
     3. mətni ingiliscə düymələrlə gəlir («OK / Cancel»), halbuki interfeys
        tam azərbaycancadır.

   ƏVƏZİNƏ: düymənin özü iki addımlı olur. Birinci klik onu «Silinsin?»
   vəziyyətinə keçirir, ikinci klik silir. 5 saniyə ərzində toxunulmasa,
   düymə öz halına qayıdır; Escape və başqa yerə klik də ləğv edir.

   REAL SƏBƏB: silmə TƏSDİQSİZ idi - admin panelində bir klik kataloqu,
   onun bütün qiymətlərini və yetim qalan məhsulları geri dönməz silirdi.
   ============================================================================ */

const DELETE_CONFIRM_MS = 5000;
let pendingDelete = null;   // {btn, label, timer}

/** Düyməni ilkin (ikon) halına qaytarır. */
function cancelPendingDelete() {
  if (!pendingDelete) return;
  const { btn, label, html, timer } = pendingDelete;
  clearTimeout(timer);
  btn.classList.remove("is-confirming");
  // İlkin məzmun BƏRPA olunur (ikon sabit deyil - səbət çipində başqa ola bilər).
  btn.innerHTML = html;
  btn.setAttribute("aria-label", label);
  pendingDelete = null;
}

/**
 * Bir «sil» düyməsini iki addımlı edir.
 *
 * `onConfirm` yalnız İKİNCİ klikdə çağırılır - silmə əməliyyatının özü
 * çağıran tərəfdə qalır, bu funksiya yalnız təsdiq mexanikasını bilir.
 */
function armDeleteButton(btn, onConfirm) {
  const label = btn.getAttribute("aria-label") || "Sil";
  const html = btn.innerHTML;

  btn.addEventListener("click", async (event) => {
    event.stopPropagation();

    // İkinci klik - HƏQİQİ silmə yalnız burada baş verir.
    if (pendingDelete && pendingDelete.btn === btn) {
      cancelPendingDelete();
      btn.disabled = true;
      await onConfirm();
      return;
    }

    // Birinci klik - başqa sətirdə gözləyən təsdiq varsa, o ləğv olunur.
    cancelPendingDelete();
    btn.classList.add("is-confirming");
    btn.textContent = t("common.confirmDelete");
    btn.setAttribute("aria-label", t("confirm.aria", { label }));
    pendingDelete = {
      btn,
      label,
      html,
      timer: setTimeout(cancelPendingDelete, DELETE_CONFIRM_MS),
    };
  });
}

// Başqa yerə klik və Escape təsdiqi ləğv edir - istifadəçi «silinsin?»
// vəziyyətini qəsdən tərk edə bilməlidir.
document.addEventListener("click", cancelPendingDelete);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") cancelPendingDelete();
});
