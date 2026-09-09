// Market səhifəsi: bir marketin endirimləri və məhsulları.
//
// Ana səhifədəki loqo şəbəkəsindən buraya keçilir. Slug ünvandan oxunur —
// `/store/araz`.
//
// DATASI OLMAYAN MARKET SƏHV DEYİL. Bazar Store və Rahat Market üçün mənbə
// hələ çəkilə bilmir. Belə halda səhifə boş qalmır: nə vəziyyətdə olduğu
// açıq yazılır. Kartı ana səhifədə kliklənməz etmək daha asan olardı, amma
// o zaman istifadəçi səbəbi heç yerdə görməzdi.

(() => {
  const slug = decodeURIComponent(location.pathname.split("/").pop());
  const el = (id) => document.getElementById(id);

  function renderHead(market) {
    document.title = `${market.name} — BasketIQ`;

    // Loqo varsa şəkil, yoxdursa marketin adı (uydurma loqo çəkmirik).
    const logo = market.logo
      ? `<img class="store-logo" src="${esc(market.logo)}" alt="${esc(market.name)}">`
      : "";
    const boxClass = market.logo
      ? "store-logo-box is-lg has-logo"
      : "store-logo-box is-lg";

    el("storeHead").innerHTML =
      `<div class="product-head">` +
      `<span class="${boxClass}">${logo}` +
      `<span class="store-wordmark">${esc(market.name)}</span></span>` +
      `<div class="product-head-text">` +
      `<h1 class="page-title">${esc(market.name)}</h1>` +
      `<p class="page-sub">` +
      (market.available
        ? `${t("store.priceCount", { n: market.products })}`
        : `${t("store.noSource")}`) +
      `</p></div></div>`;

    const img = el("storeHead").querySelector("img.store-logo");
    if (img) {
      img.addEventListener("error", () => {
        img.closest(".store-logo-box")?.classList.remove("has-logo");
        img.remove();
      });
    }
  }

  function renderSoon(market) {
    el("soonBox").innerHTML =
      `<div class="notice warn"><strong>${t("store.soonTitle")}</strong> ${t("store.soonBody", { store: esc(market.name) })}` +
      `` +
      `` +
      `` +
      `</div>`;
  }

  /** Endirim kartı — ana səhifədəki kartla eyni quruluş. */
  function dealCard(deal) {
    const size = deal.size ? `<span class="deal-size">${esc(deal.size)}</span>` : "";

    // Digər marketlərdəki qiymət: endirim faizi tək başına aldadıcıdır.
    const others = (deal.offers || []).filter((o) => o.store_slug !== slug);
    const compare = others.length
      ? `<div class="deal-offers">` +
        others
          .map(
            (o) =>
              `<div class="deal-offer${o.is_cheapest ? " is-best" : ""}">` +
              `<span class="deal-offer-store">${storeAvatar(o.store, "is-xs")}` +
              `${esc(o.store_short)}</span>` +
              `<span class="deal-offer-price">${price(o.price)}</span></div>`
          )
          .join("") +
        `</div>`
      : `<div class="deal-single">${t("store.notFoundElsewhere")}</div>`;

    return (
      `<a class="deal card-lift" href="/product/${deal.product_id}">` +
      `<div class="deal-top">` +
      `<span class="avatar is-sm">${icon(categoryIcon(deal.category))}</span>` +
      `<span class="deal-pct">−${deal.discount_pct.toFixed(0)}%</span>` +
      `</div>` +
      `<div class="deal-name">${esc(deal.label)}</div>` +
      size +
      `<div class="deal-price">` +
      `<span class="deal-now">${price(deal.price)}</span>` +
      `<span class="deal-was">${price(deal.old_price)}</span>` +
      `</div>` +
      compare +
      `</a>`
    );
  }

  function renderDeals(deals) {
    if (!deals.length) return;
    StoreColors.note(deals.flatMap((d) => (d.offers || []).map((o) => o.store)));
    el("storeDealsGrid").innerHTML = deals.map(dealCard).join("");
    el("storeDealsCard").classList.remove("hidden");
  }

  function renderProducts(products) {
    if (!products.length) return;

    const rows = products
      .map((p) => {
        const old = p.old_price
          ? `<span class="cell-sub old">${money(p.old_price)} ₼</span>`
          : "";
        return (
          `<tr><td><div class="entity">` +
          `<span class="avatar is-sm">${icon(categoryIcon(p.category))}</span>` +
          `<div class="entity-text">` +
          `<div class="entity-name"><a class="link" href="/product/${p.product_id}">` +
          `${esc(p.label)}</a></div>` +
          `<div class="entity-meta">${esc(p.size || "")}</div>` +
          `</div></div></td>` +
          `<td class="num">${price(p.price)}${old}</td></tr>`
        );
      })
      .join("");

    el("storeProductsBox").innerHTML =
      `<div class="table-scroll"><table class="lines">` +
      `<thead><tr><th>${t("common.product")}</th><th class="num">${t("common.price")}</th></tr></thead>` +
      `<tbody>${rows}</tbody></table></div>`;
    el("storeProductsCard").classList.remove("hidden");
  }

  async function load() {
    await window.IconsReady;

    let data;
    try {
      const res = await fetch(`/api/catalog/store/${encodeURIComponent(slug)}`);
      if (res.status === 404) {
        el("storeHead").innerHTML =
          `<h1 class="page-title">${t("store.notFound")}</h1>` +
          `<p class="page-sub">${t("store.notFoundBody")} ` +
          `<a class="link" href="/">${t("store.backHome")}</a>.</p>`;
        return;
      }
      data = await res.json();
    } catch (e) {
      console.error("[store]", e);
      el("soonBox").innerHTML =
        `<div class="notice error">${t("store.loadError")}</div>`;
      return;
    }

    const market = data.market;
    StoreColors.note([market.name]);
    renderHead(market);

    if (!market.available) {
      renderSoon(market);
      return;
    }

    renderDeals(data.deals || []);
    renderProducts(data.products || []);
  }

  load();

  // Dil dəyişəndə bu blok yenidən çəkilir - səhifə yenilənmir.
  // `i18n.js` hadisəni `document`-ə atır, hər modul yalnız ÖZ hissəsinə
  // baxır; beləcə heç bir modul digərinin DOM-una toxunmur.
  document.addEventListener("basketiq:lang", () => load());
})();
