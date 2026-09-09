// Axtarış / kateqoriya nəticələri: şəkilli kart şəbəkəsi + filtrlər.
//
// FİLTR VƏZİYYƏTİ ÜNVANDADIR, JS DƏYİŞƏNİNDƏ YOX.
// `/search?q=süd&market=araz&category=içkilər&max_price=5` — yəni nəticə
// paylaşıla və brauzerin «geri» düyməsi ilə gəzilə bilər. Vəziyyəti yalnız
// yaddaşda saxlasaydıq, istifadəçi filtri seçib linki göndərəndə qarşı tərəf
// başqa səhifə görərdi.
//
// FİLTRLƏR REAL DATADAN QURULUR (`facets`): boş kateqoriya menyuda görünmür.

(() => {
  const el = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);

  const state = {
    q: params.get("q") || "",
    market: params.get("market") || "",
    category: params.get("category") || "",
    max_price: params.get("max_price") || "",
  };

  let markets = [];

  /** Vəziyyəti ünvana yazır və səhifəni yenidən yükləyir. */
  function apply(changes) {
    const next = new URLSearchParams();
    const merged = { ...state, ...changes };
    for (const [key, value] of Object.entries(merged)) {
      if (value) next.set(key, value);
    }
    location.search = next.toString();
  }

  // ------------------------------------------------------------- filtrlər

  function renderFilters(facets) {
    const marketOptions = markets
      .filter((m) => m.available)
      .map(
        (m) =>
          `<label class="filter-opt">` +
          `<input type="radio" name="market" value="${esc(m.slug)}"` +
          `${state.market === m.slug ? " checked" : ""}>` +
          `<span>${esc(m.name)}</span>` +
          `<small>${m.products}</small></label>`
      )
      .join("");

    const catOptions = facets.categories
      .map(
        (c) =>
          `<label class="filter-opt">` +
          `<input type="radio" name="category" value="${esc(c.name)}"` +
          `${state.category === c.name ? " checked" : ""}>` +
          `<span>${esc(t("cat." + c.name, c.name))}</span>` +
          `<small>${c.count}</small></label>`
      )
      .join("");

    const max = facets.price?.max ? Math.ceil(facets.price.max) : 100;
    const current = state.max_price || max;

    el("filters").innerHTML =
      `<div class="filter-head">` +
      `<svg aria-hidden="true"><use href="#icon-filter"></use></svg>` +
      `<h2 class="filter-title">${t("search.filters")}</h2>` +
      (state.market || state.category || state.max_price
        ? `<button class="btn-link" id="clearFilters" type="button">${t("search.clear")}</button>`
        : "") +
      `</div>` +
      `<div class="filter-group"><h3 class="filter-label">Market</h3>` +
      `<div id="marketFilter">${marketOptions}</div></div>` +
      `<div class="filter-group"><h3 class="filter-label">Kateqoriya</h3>` +
      `<div id="categoryFilter">${catOptions}</div></div>` +
      `<div class="filter-group"><h3 class="filter-label">${t("search.maxPrice")}</h3>` +
      `<input type="range" id="priceRange" min="1" max="${max}" value="${current}" step="1">` +
      `<div class="filter-price"><span id="priceValue">${current} ₼</span></div></div>`;

    el("marketFilter").addEventListener("change", (e) =>
      apply({ market: e.target.value })
    );
    el("categoryFilter").addEventListener("change", (e) =>
      apply({ category: e.target.value })
    );

    const range = el("priceRange");
    // `input` sürüşdürərkən yalnız RƏQƏMİ yeniləyir, `change` isə buraxanda
    // sorğunu göndərir - hər piksel üçün səhifə yenilənməsin.
    range.addEventListener("input", () => {
      el("priceValue").textContent = `${range.value} ₼`;
    });
    range.addEventListener("change", () =>
      apply({ max_price: range.value >= max ? "" : range.value })
    );

    const clear = el("clearFilters");
    if (clear) {
      clear.addEventListener("click", () =>
        apply({ market: "", category: "", max_price: "" })
      );
    }
  }

  // -------------------------------------------------------------- nəticə

  function card(item) {
    const size = item.size ? `<span class="size-pill">${esc(item.size)}</span>` : "";
    const off = item.discount_pct
      ? `<span class="pcard-flag">−${item.discount_pct.toFixed(0)}%</span>`
      : "";
    const stores =
      item.store_count > 1
        ? `<span class="pcard-stores">${t("search.storeCount", { n: item.store_count })}</span>`
        : "";

    // KART ARTIQ <a> DEYİL, <div>-dir.
    //
    // Səbəb HTML qaydasıdır: keçidin (`<a>`) içinə düymə qoymaq olmaz -
    // brauzer onu ya keçid, ya düymə kimi oxuyur və klaviatura naviqasiyası
    // pozulur. İndi kartın İÇİNDƏ keçid var, düymə isə onun yanındadır.
    return (
      `<div class="pcard">` +
      `<a class="pcard-link" href="/product/${item.product_id}">` +
      `<span class="pcard-photo">${off}${productThumb(item)}</span>` +
      `<span class="pcard-body">` +
      (item.brand ? `<span class="pcard-brand">${esc(item.brand)}</span>` : "") +
      `<span class="pcard-name">${esc(item.label)}</span>` +
      `<span class="pcard-meta">${size}${stores}</span>` +
      `<span class="pcard-price">${price(item.price)}</span>` +
      `</span></a>` +
      addButton(item.product_id, "pcard-add") +
      `</div>`
    );
  }

  function renderResults(data) {
    const grid = el("resultsGrid");
    if (!data.items.length) {
      grid.innerHTML =
        `<div class="notice warn">${t("search.nothing")}` +
        `</div>`;
      el("resultsCount").textContent = "";
      return;
    }
    grid.innerHTML = data.items.map(card).join("");
    el("resultsCount").textContent = t("search.found", { n: data.total });
  }

  function renderTitle() {
    const bits = [];
    if (state.q) bits.push(`«${state.q}»`);
    if (state.category) bits.push(state.category);
    const market = markets.find((m) => m.slug === state.market);
    if (market) bits.push(market.name);

    el("resultsTitle").textContent = bits.length
      ? bits.join(" · ")
      : t("search.allProducts");
  }

  // ------------------------------------------------------------------ start

  /**
   * KART SKELETİ (P2) — cavab gələnə qədər nəticə şəbəkəsinin FORMASI görünür.
   *
   * Əvvəl burada tək sətirlik «Yüklənir» yazısı vardı: səhifənin qalan
   * hissəsi ağ qalır, sonra kartlar birdən düşürdü və məzmun SIÇRAYIRDI.
   * Skelet gələcək kartların ölçüsünü tutur - yükləmə bitəndə heç nə yerini
   * dəyişmir.
   */
  function showSkeleton(say = 8) {
    // Kartlar BİRBAŞA `#resultsGrid`-in içinə gedir: o, onsuz da şəbəkədir.
    // Ayrıca qab əlavə etsək, şəbəkə içində şəbəkə yaranır və kartlar tək
    // sütuna düzülür (brauzerdə görüldü).
    el("resultsGrid").innerHTML = Array.from(
      { length: say },
      () => `<div class="skeleton-row skeleton-card"></div>`
    ).join("");
  }

  async function load() {
    showSkeleton();
    await window.IconsReady;

    el("topSearchInput").value = state.q;

    const query = new URLSearchParams();
    if (state.q) query.set("q", state.q);
    if (state.market) query.set("market", state.market);
    if (state.category) query.set("category", state.category);
    if (state.max_price) query.set("max_price", state.max_price);
    query.set("limit", "60");

    try {
      const [data, marketList] = await Promise.all([
        fetch(`/api/catalog/search?${query}`).then((r) => r.json()),
        fetch("/api/catalog/markets").then((r) => r.json()),
      ]);
      markets = marketList.items || [];

      renderTitle();
      renderFilters(data.facets);
      renderResults(data);
    } catch (e) {
      console.error("[search]", e);
      el("resultsGrid").innerHTML =
        `<div class="notice error">${t("search.loadError")}</div>`;
    }
  }

  load();

  // Dil dəyişəndə bu blok yenidən çəkilir - səhifə yenilənmir.
  // `i18n.js` hadisəni `document`-ə atır, hər modul yalnız ÖZ hissəsinə
  // baxır; beləcə heç bir modul digərinin DOM-una toxunmur.
  document.addEventListener("basketiq:lang", () => load());
})();
