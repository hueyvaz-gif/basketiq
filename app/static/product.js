// Məhsul səhifəsi — trolley quruluşu: solda kimlik, sağda qiymətlər.
//
// SƏHİFƏNİN QAYDASI: HƏR BÖLMƏ ÖZ DATASINA GÖRƏ VAR OLUR.
// Variant yoxdursa «Ölçülər» yoxdur; ikinci müşahidə yoxdursa qiymət zolağı
// yoxdur; model əlçatmazdırsa AI qeydi yoxdur. Boş bölmə istifadəçiyə
// «burada nəsə sındı» kimi görünür — halbuki sadəcə həmin data bizdə yoxdur.
//
// RƏY BÖLMƏSİ YOXDUR və uydurulmur: layihədə nə istifadəçi hesabı, nə rəy
// cədvəli var.

(() => {
  const productId = Number(location.pathname.split("/").pop());
  const el = (id) => document.getElementById(id);

  let logos = new Map();

  // ------------------------------------------------------------ sol sütun

  function renderAside(product, offers, data) {
    document.title = `${product.label} — BasketIQ`;

    const cheapest = offers.length ? offers[0] : null;
    const brand = product.brand ? `<div class="product-brand">${esc(product.brand)}</div>` : "";
    const name = esc(
      product.brand ? product.label.replace(product.brand + " ", "") : product.label
    );
    const size = product.size ? `<span class="size-pill">${esc(product.size)}</span>` : "";

    el("productAside").innerHTML =
      brand +
      `<h1 class="product-name">${name}</h1>` +
      `<div class="product-pills">${size}` +
      (product.category ? `<span class="cat-pill">${esc(t("cat." + product.category, product.category))}</span>` : "") +
      (data.match && data.coverage && data.coverage.available > 1
        ? `<span class="match-pill ${data.match === "exact" ? "is-exact" : "is-approx"}" ` +
          `title="${esc(t(data.match === "exact" ? "match.exactHint" : "match.approximateHint"))}">` +
          `${t(data.match === "exact" ? "match.exact" : "match.approximate")}</span>`
        : "") +
      (data.coverage
        ? `<span class="coverage-pill">${t("coverage.stores", { n: data.coverage.available, total: data.coverage.total })}</span>`
        : "") +
      `</div>` +
      `<div class="product-photo">${productThumb(product)}</div>` +
      (cheapest
        ? `<div class="product-best">` +
          `<span class="eyebrow">${t("product.lowestPrice")}</span>` +
          `<span class="product-best-price">${price(cheapest.price)}</span>` +
          `<span class="product-best-store">${esc(cheapest.store)}</span>` +
          `</div>`
        : "");
  }

  // --------------------------------------------------------- «Harada al»

  function offerRow(offer) {
    const logo = logos.get(offer.store_slug);
    const mark = logo
      ? `<img class="wtb-logo" src="${esc(logo)}" alt="${esc(offer.store)}">`
      : `<span class="wtb-name">${esc(offer.store)}</span>`;

    const old = offer.old_price
      ? `<span class="wtb-old">${money(offer.old_price)} ₼</span>`
      : "";
    const unit = offer.unit_price
      ? `<div class="wtb-unit">1 ${esc(offer.base_unit)} = ${money(offer.unit_price)} ₼</div>`
      : "";

    const badges = [];
    if (offer.is_cheapest) badges.push(`<span class="tag-best">${t("product.best")}</span>`);
    if (offer.is_best_value) badges.push(`<span class="tag-value">${t("product.bestValue")}</span>`);

    return (
      `<div class="wtb-row${offer.is_cheapest ? " is-best" : ""}">` +
      `<div class="wtb-store">${mark}</div>` +
      `<div class="wtb-price">` +
      `<div class="wtb-now">${price(offer.price)} ${old}</div>` +
      unit +
      `</div>` +
      `<div class="wtb-tags">${badges.join(" ")}</div>` +
      `</div>`
    );
  }

  function renderOffers(offers, compare) {
    const box = el("offersBox");
    if (!offers.length) {
      box.innerHTML =
        `<div class="notice warn">${t("product.noPrice")}</div>`;
      return;
    }

    const summary = compare
      ? `<p class="block-sub">${t("product.spread", { n: compare.stores, amount: money(compare.spread) })} ` +
        `</p>`
      : `<p class="block-sub">${t("product.onlyOne")}</p>`;

    box.innerHTML = summary + `<div class="wtb">${offers.map(offerRow).join("")}</div>`;
  }

  /** Hansı marketin datası yoxdur — bir sətirlik izah. */
  function renderMarketNote(markets, offers) {
    const shown = new Set(offers.map((o) => o.store_slug));
    const soon = markets.filter((m) => !m.available).map((m) => m.name);
    const missing = markets
      .filter((m) => m.available && !shown.has(m.slug))
      .map((m) => m.name);

    const parts = [];
    if (missing.length) parts.push(`${t("product.missingAt", { stores: missing.join(", ") })}`);
    if (soon.length) parts.push(`${t("product.soonAt", { stores: soon.join(", ") })}`);
    el("marketNote").textContent = parts.join(" ");
  }

  // ------------------------------------------------------- qiymət zolağı

  function renderPriceBar(summary) {
    if (!summary) return;

    // Nişan zolağın kənarına yapışmasın deyə 2-98% arasında saxlanılır.
    const pos = Math.min(98, Math.max(2, summary.position));

    el("priceBar").innerHTML =
      `<div class="pricebar">` +
      `<span class="pricebar-marker" style="left:${pos}%">${money(summary.current)} ₼</span>` +
      `<span class="pricebar-track"></span>` +
      `<span class="pricebar-ends">` +
      `<span><b>${t("product.lowest")}</b> ${money(summary.lowest)} ₼</span>` +
      `<span><b>${t("product.usually")}</b> ${money(summary.usually)} ₼</span>` +
      `</span>` +
      `</div>` +
      `<p class="fineprint">${t("product.basedOn", { n: summary.observations })}</p>`;
    el("priceBarCard").classList.remove("hidden");
  }

  // ---------------------------------------------------------- variantlar

  function renderVariants(variants) {
    if (!variants.length) return;

    el("variantsBox").innerHTML =
      `<div class="size-grid">` +
      variants
        .map((v) => {
          const tag = v.is_cheapest
            ? `<span class="tag-best">Ən ucuz</span>`
            : v.is_best_value
              ? `<span class="tag-value">Ən sərfəli</span>`
              : "";
          const unit = v.unit_price
            ? `<span class="size-unit">1 ${esc(v.base_unit)} = ${money(v.unit_price)} ₼</span>`
            : "";
          const inner =
            `<span class="size-head"><span class="size-label">${esc(v.size)}</span>${tag}</span>` +
            `<span class="size-price">${price(v.price)}</span>${unit}`;

          // Cari məhsul link olmur - istifadəçi elə oradadır.
          return v.is_current
            ? `<span class="size-card is-current">${inner}</span>`
            : `<a class="size-card" href="/product/${v.product_id}">${inner}</a>`;
        })
        .join("") +
      `</div>`;
    el("variantsCard").classList.remove("hidden");
  }

  // ------------------------------------------------------ oxşar / brend

  function card(item) {
    const size = item.size ? `<span class="size-pill">${esc(item.size)}</span>` : "";
    return (
      `<a class="pcard" href="/product/${item.product_id}">` +
      `<span class="pcard-photo">${productThumb(item)}</span>` +
      `<span class="pcard-body">` +
      (item.brand ? `<span class="pcard-brand">${esc(item.brand)}</span>` : "") +
      `<span class="pcard-name">${esc(item.label)}</span>` +
      `<span class="pcard-meta">${size}</span>` +
      `<span class="pcard-price">${price(item.price)}</span>` +
      `</span></a>`
    );
  }

  function renderGrid(items, boxId, cardId) {
    if (!items.length) return;
    el(boxId).innerHTML = items.map(card).join("");
    el(cardId).classList.remove("hidden");
  }

  // ------------------------------------------------------------ AI qeydi

  async function loadNote() {
    try {
      const data = await (await fetch(`/api/catalog/product/${productId}/note`)).json();
      if (!data.available || !data.text) return;
      // Model mətni ETİBARSIZDIR: `textContent` ilə yazılır, HTML kimi yox.
      el("noteText").textContent = data.text;
      el("noteFacts").textContent = data.facts || "";
      el("noteCard").classList.remove("hidden");
    } catch (e) {
      console.error("[note]", e);
    }
  }

  el("noteFactsBtn").addEventListener("click", () => {
    el("noteFacts").classList.toggle("hidden");
  });

  // ------------------------------------------------------------------ start

  async function load() {
    await window.IconsReady;

    let data;
    try {
      const res = await fetch(`/api/catalog/product/${productId}`);
      if (res.status === 404) {
        el("productAside").innerHTML =
          `<h1 class="product-name">${t("product.notFound")}</h1>` +
          `<p class="block-sub"><a class="link" href="/">${t("store.backHome")}</a></p>`;
        el("offersBox").innerHTML = "";
        return;
      }
      data = await res.json();
    } catch (e) {
      console.error("[product]", e);
      el("offersBox").innerHTML = `<div class="notice error">${t("product.loadError")}</div>`;
      return;
    }

    const offers = data.offers || [];
    const markets = data.markets || [];
    logos = new Map(markets.filter((m) => m.logo).map((m) => [m.slug, m.logo]));
    StoreColors.note(markets.map((m) => m.name));

    renderAside(data.product, offers, data);
    renderOffers(offers, data.compare);
    renderMarketNote(markets, offers);
    renderPriceBar(data.price_summary);
    renderVariants(data.variants || []);
    renderGrid(data.same_brand || [], "brandBox", "brandCard");
    renderGrid(data.similar || [], "similarBox", "similarCard");

    loadNote();
  }

  load();

  // Dil dəyişəndə bu modul öz blokunu yenidən çəkir - səhifə yenilənmir.
  document.addEventListener("basketiq:lang", () => {
    load();
  });
})();
