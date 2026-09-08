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
        ? `${market.products} məhsulun qiyməti bizdədir.`
        : `Bu marketin data mənbəyi hələ hazır deyil.`) +
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
      `<div class="notice warn"><strong>Tezliklə.</strong> ` +
      `${esc(market.name)} üçün qiymət mənbəyi hələ qoşulmayıb, ona görə ` +
      `burada göstərəcək qiymətimiz yoxdur. Qoşulan kimi məhsullar bu ` +
      `səhifədə görünəcək — o vaxta qədər müqayisə digər marketlərlə aparılır.` +
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
      : `<div class="deal-single">Digər marketlərdə tapılmadı</div>`;

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
      `<thead><tr><th>Məhsul</th><th class="num">Qiymət</th></tr></thead>` +
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
          `<h1 class="page-title">Market tapılmadı</h1>` +
          `<p class="page-sub">Bu ünvanda market yoxdur. ` +
          `<a class="link" href="/">Ana səhifəyə qayıt</a>.</p>`;
        return;
      }
      data = await res.json();
    } catch (e) {
      console.error("[store]", e);
      el("soonBox").innerHTML =
        `<div class="notice error">Market datası yüklənmədi.</div>`;
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
})();
