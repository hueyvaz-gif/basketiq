// Səbət müqayisəsi, axtarış, kataloq emalı və sistem statusu.
//
// Fayl iki paneli birlikdə idarə edir (istifadəçi + admin), amma DOM-un
// hansı paneldə olduğu burada əhəmiyyət daşımır: hər şey ID ilə tapılır,
// panel keçidi isə nav.js-in işidir.

const $ = (sel) => document.querySelector(sel);
let selectedFile = null;

// ---------------------------------------------------------------- yardımçılar

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
 * Market = ikon + ad.
 *
 * Real logo YOXDUR: `stores` cədvəlində yalnız slug/name/website var.
 * Saxta loqo çəkmək əvəzinə hamısına eyni mağaza ikonu verilir - market
 * adı isə mətn kimi qalır, yəni heç bir məlumat itmir.
 */
const storeChip = (name, best = false) =>
  `<span class="store-chip${best ? " is-best" : ""}">` +
  `<span class="store-mark" style="color:${StoreColors.cssVar(name)}">${icon("store")}</span>` +
  `${esc(name)}</span>`;

/**
 * Marketə SABİT rəng nöqtəsi.
 *
 * Xananı `store-colors.js` hesablayır - BURADA REYESTR SAXLAMIRIQ. Rəng ADDAN
 * gəlir, sıra indeksindən yox: `basket.py` marketləri səbət cəminə görə
 * çeşidlədiyi üçün sıra hər əlavədən sonra dəyişir, rəng isə dəyişməməlidir.
 *
 * Palitrada YAŞIL və QIRMIZI yoxdur: onlar status rəngidir. Market nöqtəsi
 * yaşıl olsa, "bu market ucuzdur?" sualı yaranardı.
 */
const storeDot = (name) =>
  `<span class="store-dot" style="background:${StoreColors.cssVar(name)}" aria-hidden="true"></span>`;

/** Valyuta işarəsi rəqəmdən nazik göstərilir - fokus ədədin üstündə qalsın. */
const price = (v) => `${money(v)}<span class="cur">₼</span>`;

function notice(el, kind, html) {
  el.innerHTML = `<div class="notice ${kind}">${html}</div>`;
}

// ---------------------------------------------------------------- fayl seçimi

const dropzone = $("#dropzone");
const fileInput = $("#fileInput");

function setFile(file) {
  selectedFile = file;
  $("#fileName").textContent = file
    ? `${file.name} — ${(file.size / 1048576).toFixed(2)} MB`
    : "Fayl seçilməyib";
  $("#uploadBtn").disabled = !file;
}

dropzone.addEventListener("click", () => fileInput.click());

// Dropzone <div>-dir, yəni klaviatura ilə "klikləmək" özü işləmir.
// role="button" verdiyimizə görə Enter/Space-i əl ilə bağlamalıyıq -
// əks halda siçansız istifadəçi fayl seçə bilmir.
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

fileInput.addEventListener("change", (e) => setFile(e.target.files[0] || null));

["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.add("over");
  })
);

["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.remove("over");
  })
);

dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

// ---------------------------------------------------------------- upload

$("#uploadBtn").addEventListener("click", async () => {
  if (!selectedFile) return;

  const form = new FormData();
  form.append("file", selectedFile);
  form.append("store", $("#storeInput").value.trim() || "Naməlum market");
  form.append("force_ocr", $("#forceOcr").checked ? "true" : "false");
  form.append("psm", $("#psmInput").value);

  $("#uploadBtn").disabled = true;
  notice(
    $("#uploadStatus"),
    "info",
    `<span class="spinner"></span>Emal olunur… Skan PDF-də OCR bir neçə dəqiqə çəkə bilər.`
  );

  try {
    const res = await fetch("/api/catalogs/upload", { method: "POST", body: form });
    const data = await res.json();

    if (!res.ok) {
      notice($("#uploadStatus"), "error", esc(data.detail || "Naməlum xəta"));
      return;
    }
    if (data.duplicate) {
      notice($("#uploadStatus"), "warn", esc(data.message));
      await loadCatalogs();
      await showLines(data.catalog_id);
      return;
    }

    notice(
      $("#uploadStatus"),
      "ok",
      `Hazırdır — <strong>${data.stats.kept}</strong> məhsul namizədi sətir tapıldı.`
    );
    renderResult(data);
    await Promise.all([loadCatalogs(), loadHealth()]);
  } catch (e) {
    notice($("#uploadStatus"), "error", "Şəbəkə xətası: " + esc(e.message));
  } finally {
    $("#uploadBtn").disabled = false;
  }
});

// ---------------------------------------------------------------- nəticə

const SOURCE_LABEL = {
  pdf_text: "PDF (text layer) — OCR-siz",
  pdf_scan: "Skan PDF — OCR",
  image: "Şəkil — OCR",
};

function renderResult(data) {
  $("#resultCard").classList.remove("hidden");
  currentCatalogId = data.catalog_id;
  $("#extractStatus").innerHTML = "";
  $("#productCard").classList.add("hidden");

  const s = data.stats;
  const dropped = Object.entries(s.dropped || {})
    .map(([k, v]) => `<span class="badge">${esc(k)} <strong>${v}</strong></span>`)
    .join("");

  $("#resultMeta").innerHTML = `
    <div class="badges">
      <span class="badge ${data.ocr_used ? "warn" : "ok"}">${esc(SOURCE_LABEL[data.source_type] || data.source_type)}</span>
      <span class="badge">səhifə <strong>${data.pages ?? "—"}</strong></span>
      <span class="badge">simvol <strong>${data.chars ?? "—"}</strong></span>
      <span class="badge">xam sətir <strong>${s.total_lines}</strong></span>
      <span class="badge ok">saxlanıldı <strong>${s.kept}</strong></span>
      <span class="badge">nisbət <strong>${(s.keep_ratio * 100).toFixed(0)}%</strong></span>
    </div>
    ${dropped ? `<div class="badges">${dropped}</div>` : ""}
    ${(data.notes || []).map((n) => `<div class="notice info">${esc(n)}</div>`).join("")}
  `;

  renderLines(data.preview || []);
}

function renderLines(lines) {
  if (!lines.length) {
    $("#linesTable").innerHTML =
      `<tr><td class="txt">Heç bir məhsul sətri tapılmadı. PSM rejimini dəyişib yenidən yoxlayın.</td></tr>`;
    return;
  }
  $("#linesTable").innerHTML = `
    <thead>
      <tr><th>#</th><th class="num">Qiymət</th><th class="num">Köhnə</th><th>Sətir</th></tr>
    </thead>
    <tbody>
      ${lines
        .map(
          (l, i) => `<tr>
            <td class="num">${i + 1}</td>
            <td class="num"><strong>${money(l.price)}</strong></td>
            <td class="num old">${l.old_price == null ? "" : money(l.old_price)}</td>
            <td class="txt">${esc(l.text)}</td>
          </tr>`
        )
        .join("")}
    </tbody>`;
}

// ---------------------------------------------------------------- AI çıxarış

let currentCatalogId = null;

$("#extractBtn").addEventListener("click", async () => {
  if (!currentCatalogId) return;

  const limit = $("#extractLimit").value;

  $("#extractBtn").disabled = true;
  notice(
    $("#extractStatus"),
    "info",
    `<span class="spinner"></span>Model sətirləri emal edir…
     <br><small>Keşdə olan sətirlər dərhal qayıdır.</small>`
  );

  try {
    const res = await fetch(`/api/catalogs/${currentCatalogId}/extract?limit=${limit}`, {
      method: "POST",
    });
    const data = await res.json();

    if (!res.ok) {
      notice($("#extractStatus"), "error", esc(data.detail || "Xəta"));
      return;
    }

    const llm = data.llm;
    notice(
      $("#extractStatus"),
      "ok",
      `<strong>${data.saved}</strong> məhsul yazıldı ·
       keşdən <strong>${llm.from_cache}</strong> ·
       modeldən <strong>${llm.from_llm}</strong> ·
       uğursuz <strong>${llm.failed}</strong>`
    );
    renderProducts(data.products, data);
    await Promise.all([loadHealth(), loadCompare()]);
  } catch (e) {
    notice($("#extractStatus"), "error", "Şəbəkə xətası: " + esc(e.message));
  } finally {
    $("#extractBtn").disabled = false;
  }
});

function renderProducts(items, meta) {
  $("#productCard").classList.remove("hidden");

  $("#productMeta").innerHTML = `
    <div class="badges">
      <span class="badge"><strong>${esc(meta.store)}</strong></span>
      <span class="badge">emal olundu <strong>${meta.processed}</strong>/${meta.total_lines}</span>
      <span class="badge ok">yazıldı <strong>${meta.saved}</strong></span>
      ${meta.skipped ? `<span class="badge warn">ötürüldü <strong>${meta.skipped}</strong></span>` : ""}
    </div>`;

  if (!items.length) {
    $("#productTable").innerHTML = `<tr><td class="txt">Məhsul çıxarılmadı.</td></tr>`;
    return;
  }

  $("#productTable").innerHTML = `
    <thead>
      <tr>
        <th>Məhsul</th><th>Brend</th><th>Ölçü</th>
        <th class="num">Qiymət</th><th class="num">Vahid qiymət</th><th>Kateqoriya</th>
      </tr>
    </thead>
    <tbody>
      ${items
        .map((p) => {
          const size = p.size_value != null && p.size_unit ? `${p.size_value} ${p.size_unit}` : "—";
          const unit = p.unit_price != null ? `${money(p.unit_price)} / ${p.base_unit}` : "—";
          return `<tr title="${esc(p.raw_line)}">
            <td class="txt">${esc(p.name)}</td>
            <td class="txt">${esc(p.brand || "—")}</td>
            <td class="num">${esc(size)}</td>
            <td class="num"><strong>${money(p.price)}</strong></td>
            <td class="num">${esc(unit)}</td>
            <td class="txt">${esc(p.category)}</td>
          </tr>`;
        })
        .join("")}
    </tbody>`;
}

async function showLines(catalogId) {
  const res = await fetch(`/api/catalogs/${catalogId}/lines?limit=200`);
  if (!res.ok) return;
  const data = await res.json();
  $("#resultCard").classList.remove("hidden");
  currentCatalogId = catalogId;
  $("#extractStatus").innerHTML = "";
  $("#productCard").classList.add("hidden");
  $("#resultMeta").innerHTML = `
    <div class="badges">
      <span class="badge"><strong>${esc(data.store)}</strong></span>
      <span class="badge">${esc(SOURCE_LABEL[data.source_type] || data.source_type)}</span>
      <span class="badge">xam sətir <strong>${data.stats.total_lines}</strong></span>
      <span class="badge ok">saxlanıldı <strong>${data.stats.kept}</strong></span>
    </div>`;
  renderLines(data.lines);
  $("#resultCard").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------------------------------------------------------------- kataloqlar

async function loadCatalogs() {
  try {
    const res = await fetch("/api/catalogs");
    const rows = await res.json();

    if (!rows.length) {
      $("#catalogList").innerHTML =
        `<div class="row"><span class="row-value">Hələ kataloq yüklənməyib.</span></div>`;
      return;
    }

    $("#catalogList").innerHTML = rows
      .map(
        (r) => `<div class="row cat-row">
          <span class="entity">
            <span class="avatar is-sm" aria-hidden="true">${icon("file")}</span>
            <span class="entity-text">
              <span class="entity-name">${esc(r.store_name)}</span>
              <span class="entity-meta">#${r.id} · ${esc(SOURCE_LABEL[r.source_type] || r.source_type)} · ${esc(r.fetched_at)}</span>
            </span>
          </span>
          <span class="actions flush">
            <button class="btn btn-secondary" data-lines="${r.id}" type="button">Sətirlər</button>
            <button class="icon-btn" data-del="${r.id}" type="button"
                    aria-label="${esc(r.store_name)} kataloqunu sil">${icon("trash")}</button>
          </span>
        </div>`
      )
      .join("");

    $("#catalogList").querySelectorAll("[data-lines]").forEach((b) =>
      b.addEventListener("click", () => showLines(b.dataset.lines))
    );
    $("#catalogList").querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", async () => {
        b.disabled = true;
        await fetch(`/api/catalogs/${b.dataset.del}`, { method: "DELETE" });
        await Promise.all([loadCatalogs(), loadHealth()]);
        $("#resultCard").classList.add("hidden");
      })
    );
  } catch {
    $("#catalogList").innerHTML = `<div class="row"><span class="row-value">Siyahı yüklənmədi</span></div>`;
  }
}

// ---------------------------------------------------------------- matching

$("#matchBtn").addEventListener("click", async () => {
  $("#matchBtn").disabled = true;
  notice($("#matchStatus"), "info",
    `<span class="spinner"></span>Oxşar məhsullar axtarılır, sonra model onları yoxlayır…`);

  try {
    const data = await (await fetch("/api/match/run?limit=20", { method: "POST" })).json();
    const pairs = (data.pairs || [])
      .map((p) => `<div class="search-item"><span>${esc(p.a)} <span class="search-meta">≡</span> ${esc(p.b)}</span>
                   <span class="search-meta">oxşarlıq ${p.similarity}</span></div>`)
      .join("");
    const rejected = (data.rejected || [])
      .map((p) => `<div class="search-item"><span class="na">${esc(p.a)} <span class="search-meta">≠</span> ${esc(p.b)}</span>
                   <span class="search-meta">oxşarlıq ${p.similarity}</span></div>`)
      .join("");

    notice($("#matchStatus"), "ok",
      `<strong>${data.llm.confirmed}</strong> cüt birləşdirildi ·
       yoxlanıldı ${data.candidates_checked}/${data.candidates_found} ·
       keşdən ${data.llm.from_cache} · modeldən ${data.llm.from_llm}
       ${pairs ? `<div class="gap-sm">${pairs}</div>` : ""}
       ${rejected ? `<div class="gap-sm is-muted">${rejected}</div>` : ""}`);

    await loadCompare();
  } catch (e) {
    notice($("#matchStatus"), "error", "Xəta: " + esc(e.message));
  } finally {
    $("#matchBtn").disabled = false;
  }
});

// ---------------------------------------------------------------- axtarış

let searchTimer = null;

$("#searchInput").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) {
    $("#searchResults").innerHTML = "";
    return;
  }
  searchTimer = setTimeout(() => runSearch(q), 250);
});

async function runSearch(q) {
  try {
    const data = await (await fetch(`/api/products/search?q=${encodeURIComponent(q)}`)).json();
    if (!data.items.length) {
      $("#searchResults").innerHTML =
        `<div class="search-item"><span class="search-meta">Tapılmadı</span></div>`;
      return;
    }
    $("#searchResults").innerHTML = data.items
      .map((p) => {
        const size = p.size_value != null && p.size_unit ? `${p.size_value} ${p.size_unit}` : "";
        const title = esc([p.brand, p.name].filter(Boolean).join(" "));
        return `<div class="search-item">
          <span class="entity">
            <span class="avatar is-sm" aria-hidden="true">${icon(categoryIcon(p.category))}</span>
            <span class="entity-text">
              <span class="entity-name">${title}</span>
              <span class="entity-meta">${esc(size)} · ${p.store_count} market</span>
            </span>
          </span>
          <button class="btn btn-secondary" data-add="${p.id}" type="button"
                  aria-label="${title} məhsulunu səbətə əlavə et">Səbətə</button>
        </div>`;
      })
      .join("");

    $("#searchResults").querySelectorAll("[data-add]").forEach((b) =>
      b.addEventListener("click", async () => {
        b.disabled = true;
        b.innerHTML = `${icon("check")} Əlavə olundu`;
        await fetch("/api/basket/items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_id: Number(b.dataset.add), qty: 1 }),
        });
        await loadCompare();
      })
    );
  } catch {
    $("#searchResults").innerHTML = "";
  }
}

// ---------------------------------------------------------------- müqayisə

/** Səbət boş / natamam olanda AI düyməsi və mətni sıfırlanır. */
function resetAdvisor(enabled) {
  $("#adviseBtn").disabled = !enabled;
  $("#advisorText").textContent = "";
  $("#advisorCheck").innerHTML = "";
  $("#factsBox").classList.add("hidden");
  const placeholder = $("#advisorPlaceholder");
  placeholder.classList.remove("hidden");
  placeholder.innerHTML = enabled
    ? `Səbətiniz hazırdır — <strong>Tövsiyə al</strong> düyməsi ilə izah alın.`
    : `Səbətinizi doldurun, sonra <strong>Tövsiyə al</strong> düyməsini basın.`;
}

/**
 * HERO: səhifənin əsas cavabı.
 *
 * Üç fərqli hal var və üçü də REAL datadan gəlir - uydurma rəqəm yoxdur:
 *   1. səbət boşdur                  -> boş hal
 *   2. heç bir market tam satmır     -> qalib elan edilmir, səbəb izah olunur
 *   3. qalib var                     -> market, cəm, (varsa) qənaət
 */
function renderHero(data) {
  const box = $("#compareResult");

  if (!data.items.length) {
    box.innerHTML = `
      <div class="hero-empty">
        <div class="hero-empty-title">Səbət boşdur</div>
        <div>Aşağıdakı axtarışdan məhsul əlavə edin — müqayisə dərhal görünəcək.</div>
      </div>`;
    return;
  }

  // QALİB YOXDUR — amma bu, "cavab yoxdur" demək deyil.
  //
  // Marketlərin assortimenti fərqli olanda heç biri səbətin hamısını satmır.
  // Köhnə versiyada burada ölü boz qutu vardı və istifadəçi ekranda BİR
  // rəqəm də görmürdü. Halbuki onun sualının cavabı var: "bu səbət ən azı
  // neçəyə başa gəlir?" Backend `cheapest` sahəsində məhz onu verir.
  if (!data.best) {
    const c = data.cheapest;
    const most = [...data.stores].sort((a, b) => b.covered - a.covered)[0];

    // `cheapest` və ya market siyahısı yoxdursa, sadə izahla kifayətlənirik.
    //
    // Bu yoxlama BOŞ YERƏ deyil: onsuz `c.total` oxunanda funksiya çöküb
    // BÜTÜN müqayisəni (cədvəl, sütunlar, AI düyməsi) render etməmiş qoyurdu -
    // yəni bir sahənin olmaması səhifənin yarısını aparırdı.
    if (!c || !most) {
      box.innerHTML = `
        <div class="hero-empty">
          <div class="hero-empty-title">Qalib elan edilmir</div>
          <div>${esc(data.note || "Heç bir market səbətin hamısını satmır.")}</div>
        </div>`;
      return;
    }

    box.innerHTML = `
      <div class="hero-body">
        <div class="hero-winner is-split">
          <div class="ribbon is-amber">Bölünmüş alış</div>
          <span class="eyebrow">Əldə edilə bilən ən ucuz cəm</span>
          <div class="hero-price">${price(c.total)}</div>
          <div class="hero-price-note">
            ${c.store_count} marketi gəzsəniz — hər məhsulu ən ucuz satandan
            ${c.unavailable ? ` · ${c.unavailable} məhsul heç bir marketdə tapılmadı` : ""}
          </div>
        </div>
        <div class="hero-aside">
          <div class="eyebrow">Tək marketlə olmur</div>
          <div class="hero-aside-note">
            ${esc(data.note || "Heç bir market səbətin hamısını satmır.")}
          </div>
          <div class="hero-aside-note">
            Ən çox əhatə: <strong>${esc(most.store)}</strong> —
            ${most.covered}/${data.items.length} məhsul.
          </div>
        </div>
      </div>`;
    return;
  }

  const best = data.best;
  // Rəqəm suffiksindən (6-sı / 6-ində) qaçırıq: say dəyişəndə şəkilçi də
  // dəyişir və şablon sətrində bunu düzgün etmək mümkün deyil.
  const leadNote =
    `Ən ucuz qiymət: ${best.cheapest_count} / ${data.items.length} məhsulda`;

  // Qənaət YALNIZ ən azı iki TAM səbət olanda hesablanır (backend belə verir).
  // Yoxdursa uydurmuruq - istifadəçiyə səbəbi deyirik.
  const savingBlock = data.savings
    ? `<div class="eyebrow">Qənaət</div>
       <div class="hero-saving">${price(data.savings)}</div>
       <div class="hero-aside-note">
         ən bahalı tam səbətlə müqayisədə
       </div>`
    : `<div class="eyebrow">Qənaət</div>
       <div class="hero-aside-note">
         Qənaəti hesablamaq üçün səbətin hamısını satan ən azı iki market lazımdır.
       </div>`;

  // GUŞƏ LENTİ. Faiz REAL datadan hesablanır, uydurulmur:
  //   ən bahalı tam səbət = best.total + savings
  //   qənaət faizi        = savings / ən bahalı × 100
  // `savings` yalnız ən azı İKİ tam səbət olanda gəlir (backend belə verir);
  // olmayanda faiz də yazılmır - lent neytral mətnə düşür.
  const ribbonText = data.savings
    ? `${Math.round((data.savings / (best.total + data.savings)) * 100)}% ucuz`
    : "Ən sərfəli";

  box.innerHTML = `
    <div class="hero-body">
      <div class="hero-winner">
        <div class="ribbon">${esc(ribbonText)}</div>
        <span class="eyebrow">Ən sərfəli seçim</span>
        <div class="hero-winner-id gap-sm">
          <span class="avatar is-lg" aria-hidden="true">${icon("store")}</span>
          <div class="hero-store">${esc(best.store)}</div>
        </div>
        <div class="hero-price">${price(best.total)}</div>
        <div class="hero-price-note">${esc(leadNote)}</div>
      </div>
      <div class="hero-aside">${savingBlock}</div>
    </div>`;
}

/**
 * Marketlərin yan-yana müqayisəsi.
 *
 * TƏLƏ: natamam marketin cəmi kiçikdir, çünki çatışmayan məhsul 0 sayılır.
 * Yəni onun sütunu QISA, deməli "ucuz" görünür. Ona görə belə sütun zolaqlı
 * çəkilir və yanında "6/7 məhsul" yazılır - rəng tək siqnal deyil.
 */
function renderBars(data) {
  const box = $("#storeBars");
  if (!data.stores.length) {
    box.innerHTML = "";
    return;
  }

  // Səbətdən HEÇ NƏ satmayan market ayrıca göstərilir.
  //
  // Niyə? Onun cəmi 0.00-dır, yəni bar çəksək ən qısa - deməli "ən ucuz" -
  // görünərdi. Bu, yalan olardı: market ucuz deyil, sadəcə bu məhsulları
  // satmır. Ona görə bar əvəzinə açıq mətn yazılır.
  const selling = data.stores.filter((s) => s.covered > 0);
  const notSelling = data.stores.filter((s) => s.covered === 0);

  const max = Math.max(...selling.map((s) => s.total), 0.01);

  const emptyRows = notSelling
    .map(
      (s) => `<div class="bar-row is-empty">
        <div class="bar-name">
          <span class="avatar is-sm" style="color:${StoreColors.cssVar(s.store)}"
                aria-hidden="true">${icon("store")}</span>
          <span>${esc(s.store)}<small>səbətdəki məhsulları satmır</small></span>
        </div>
        <div class="bar-empty">Müqayisədə iştirak etmir</div>
      </div>`
    )
    .join("");

  box.innerHTML = `<div class="bars">${selling
    .map((s) => {
      const isBest = data.best && s.store_id === data.best.store_id;
      const cls = `bar-row${isBest ? " is-best" : ""}${s.complete ? "" : " is-partial"}`;
      const sub = s.complete
        ? (isBest ? "ən ucuz tam səbət" : (s.diff != null ? `+${money(s.diff)} ₼` : ""))
        : `${s.covered}/${data.items.length} məhsul — natamam`;
      // Bar ən azı 22% enində olur ki, içindəki rəqəm həmişə oxunsun
      const width = Math.max(22, (s.total / max) * 100);
      return `<div class="${cls}">
        <div class="bar-name">
          <span class="avatar is-sm" style="color:${StoreColors.cssVar(s.store)}"
                aria-hidden="true">${icon("store")}</span>
          <span>${esc(s.store)}<small>${esc(sub)}</small></span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${width.toFixed(1)}%"></div>
          <div class="bar-value">${price(s.total)}</div>
        </div>
      </div>`;
    })
    .join("")}${emptyRows}</div>
    ${data.note ? `<div class="notice warn">${esc(data.note)}</div>` : ""}`;
}

/** Məhsul × market cədvəli. Ən ucuz xana yaşıl fon + işarə ilə vurğulanır. */
function renderCompareTable(data) {
  const stores = data.stores;

  $("#compareTableWrap").innerHTML = `
    <div class="table-scroll">
      <table class="lines">
        <caption class="sr-only">Səbətdəki məhsulların marketlər üzrə qiymət müqayisəsi</caption>
        <thead>
          <tr>
            <th scope="col">Məhsul</th>
            ${stores
              .map((s) => {
                const best = data.best && s.store_id === data.best.store_id;
                return `<th scope="col" class="num">${storeChip(s.store, best)}</th>`;
              })
              .join("")}
            <th scope="col"><span class="sr-only">Əməliyyat</span></th>
          </tr>
        </thead>
        <tbody>
          ${data.items
            .map((item) => {
              const cells = stores
                .map((s) => {
                  const p = item.prices[String(s.store_id)];
                  if (!p) return `<td class="num na">—</td>`;
                  const cheap = item.cheapest_store_id === s.store_id;
                  // Ən ucuz qiymət YAŞIL PILL içindədir.
                  // Rəng TƏK siqnal deyil: pillin içində ikon və ekran
                  // oxuyucusu üçün gizli mətn də var, yəni rəngi ayırd edə
                  // bilməyən istifadəçi məlumatı itirmir.
                  const inner = cheap
                    ? `<span class="price-pill is-best">${icon("check")}${money(p.price)}` +
                      `<span class="sr-only">— ən ucuz</span></span>`
                    : price(p.price);
                  return `<td class="num" title="${esc(p.raw_line || "")}">${inner}</td>`;
                })
                .join("");
              return `<tr>
                <td class="txt">
                  <span class="entity">
                    <span class="avatar" aria-hidden="true">${icon(categoryIcon(item.category))}</span>
                    <span class="entity-text">
                      <span class="entity-name">${esc(item.label)}</span>
                      <span class="entity-meta">${esc([item.size, item.category].filter(Boolean).join(" · "))}</span>
                    </span>
                  </span>
                </td>
                ${cells}
                <td class="num">
                  <button class="icon-btn" data-del-item="${item.product_id}" type="button"
                          aria-label="${esc(item.label)} məhsulunu səbətdən sil">${icon("trash")}</button>
                </td>
              </tr>`;
            })
            .join("")}
        </tbody>
      </table>
    </div>`;

  $("#compareTableWrap").querySelectorAll("[data-del-item]").forEach((b) =>
    b.addEventListener("click", async () => {
      b.disabled = true;
      await fetch(`/api/basket/items/${b.dataset.delItem}`, { method: "DELETE" });
      await loadCompare();
    })
  );
}

async function loadCompare() {
  try {
    const data = await (await fetch("/api/basket/compare")).json();

    // Rəng xanaları RENDERDƏN ƏVVƏL paylanır: sətirlər tək-tək çəkilərkən
    // dəst böyüsəydi, ilk sətirlər köhnə xananı saxlayardı və eyni market
    // cədvəldə bir, barlarda başqa rəngdə görünərdi.
    StoreColors.note(data.stores.map((s) => s.store));

    renderHero(data);

    if (!data.items.length) {
      $("#storeBars").innerHTML = "";
      $("#compareTableWrap").innerHTML =
        `<div class="hint">Səbətdə məhsul yoxdur.</div>`;
      resetAdvisor(false);
      return;
    }

    renderBars(data);
    renderCompareTable(data);
    // Səbət dəyişdisə köhnə tövsiyə artıq doğru deyil - sıfırlanır
    resetAdvisor(true);
  } catch {
    $("#compareResult").innerHTML =
      `<div class="notice error">Müqayisə yüklənmədi — backend cavab vermir.</div>`;
    resetAdvisor(false);
  }
}

// ---------------------------------------------------------------- health

/** Statistika kartları — ikon + etiket + rəqəm + izah. */
function renderStats(db) {
  // Dördü də NEYTRAL inventar sayğacıdır: "Məhsul" qənaət deyil, "Qiymət"
  // diqqət tələb etmir. Əvvəl yaşıl/kəhrəba sırf "hamısı mavi olmasın" deyə
  // verilirdi - rəng bəzək kimi işlədilirdi. Üstəlik index.html-dəki skeleton
  // is-accent ilə başlayırdı, yəni yüklənəndə rəng sıçrayırdı.
  const cards = [
    ["store", "Market", db.stores, "Qiyməti olan supermarket", "is-accent"],
    ["layers", "Kataloq", db.catalogs, "Emal olunmuş fayl", "is-accent"],
    ["package", "Məhsul", db.products, "AI ilə çıxarılmış sətir", "is-accent"],
    ["tag", "Qiymət", db.prices, "Ümumi müşahidə", "is-accent"],
  ];

  $("#stats").innerHTML = cards
    .map(
      ([ico, label, value, note, tone]) => `
      <div class="stat ${tone}">
        <div class="stat-icon">${icon(ico)}</div>
        <div class="stat-label">${label}</div>
        <div class="stat-value">${value ?? "—"}</div>
        <div class="stat-note">${note}</div>
      </div>`
    )
    .join("");
}

/**
 * Admin panelindəki status xanası: ikon + etiket + vəziyyət.
 *
 * `state` üç dəyər alır - true / false / null. Nöqtənin rəngi ondan gəlir,
 * amma rəng TƏK siqnal deyil: `sr-only` mətn vəziyyəti sözlə də deyir.
 */
function statusTile(ico, label, state, value, detail = "") {
  const cls = state === true ? "ok" : state === false ? "bad" : "warn";
  const tone = state === true ? "is-green" : state === false ? "" : "is-amber";
  const word = state === true ? "işləyir" : state === false ? "xəta" : "yoxlanılır";
  return `<div class="status-tile">
    <span class="avatar is-sm ${tone}" aria-hidden="true">${icon(ico)}</span>
    <div class="status-tile-body">
      <span class="eyebrow">${esc(label)}</span>
      <div class="status-value">
        <span class="dot ${cls}"></span>${esc(value)}
        <span class="sr-only"> — ${word}</span>
      </div>
      ${detail ? `<div class="status-detail">${esc(detail)}</div>` : ""}
    </div>
  </div>`;
}

async function loadHealth() {
  try {
    const data = await (await fetch("/health")).json();
    if (!data.database.error) renderStats(data.database);

    const llm = data.llm;
    // Aktiv model: Claude işləyirsə o, əks halda Ollama (bax: ai/llm.py).
    const activeModel = llm.claude_active ? llm.claude_model : llm.model;

    $("#status").innerHTML = [
      statusTile("database", "Verilənlər bazası", !data.database.error,
        data.database.error ? "Xəta" : "Qoşuludur",
        data.database.error || ""),
      statusTile("sparkle", "LLM provayderi", llm.claude_active || llm.reachable,
        llm.status || llm.provider,
        llm.claude_note || ""),
      statusTile("cpu", "Aktiv model", llm.claude_active || llm.model_available,
        activeModel,
        llm.claude_active ? "Ehtiyat: " + llm.model : ""),
      statusTile("server", "Ollama serveri", llm.reachable,
        llm.reachable ? "Əlçatandır" : "Əlçatmazdır",
        llm.reachable ? llm.base_url : (llm.error || "")),
      statusTile("terminal", "Mühit", true, data.env),
    ].join("");
  } catch {
    $("#status").innerHTML = statusTile("server", "Backend", false, "Cavab vermir",
      "uvicorn işləyirmi?");
  }
}

loadHealth();
loadCatalogs();
loadCompare();
