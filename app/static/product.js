// Məhsul səhifəsi: harada al, ölçü variantları, AI qeydi, oxşar məhsullar.
//
// SƏHİFƏNİN QAYDASI: HƏR BÖLMƏ ÖZ DATASINA GÖRƏ VAR OLUR.
// Variant yoxdursa «Ölçü variantları» kartı çəkilmir; brend yoxdursa «Eyni
// brenddən» yoxdur; model əlçatmazdırsa «AI qeydi» yoxdur. Boş kart
// istifadəçiyə "burada nəsə olmalı idi, amma sındı" kimi görünür — halbuki
// sadəcə həmin data bizdə yoxdur.
//
// AI QEYDİ AYRICA SORĞUDUR: baza cavabı millisaniyələrlə, model cavabı
// saniyələrlə gəlir. Bir sorğuda birləşdirsək, cədvəl də modeli gözləyərdi.

(() => {
  const productId = Number(location.pathname.split("/").pop());

  const el = (id) => document.getElementById(id);

  /** «2 marketdə» sətri — say sözlə yazılır, rəqəm tək başına quru qalmasın. */
  const storeCountText = (n) =>
    n === 1 ? "1 marketdə tapılıb" : `${n} marketdə tapılıb`;

  // ------------------------------------------------------------------ başlıq

  function renderHead(product, offers) {
    const meta = [product.size, product.category].filter(Boolean);
    const cheapest = offers.length ? offers[0] : null;

    document.title = `${product.label} — BasketIQ`;

    el("productHead").innerHTML =
      `<div class="product-head">` +
      `<span class="avatar is-lg">${icon(categoryIcon(product.category))}</span>` +
      `<div class="product-head-text">` +
      `<h1 class="page-title">${esc(product.label)}</h1>` +
      `<p class="page-sub">${meta.map(esc).join(" · ")}</p>` +
      `</div>` +
      (cheapest
        ? `<div class="product-head-price">` +
          `<div class="eyebrow">Ən ucuz</div>` +
          `<div class="product-price">${price(cheapest.price)}</div>` +
          `<div class="product-price-store">${esc(cheapest.store)}</div>` +
          `</div>`
        : "") +
      `</div>`;
  }

  // ---------------------------------------------------------------- harada al

  function renderOffers(offers, compare) {
    const box = el("offersBox");

    if (!offers.length) {
      // Qiyməti olmayan məhsul: xəta deyil, sadəcə datamız yoxdur.
      box.innerHTML =
        `<div class="notice warn">Bu məhsulun heç bir marketdə cari qiyməti yoxdur. ` +
        `Kataloq yenilənəndə qiymət burada görünəcək.</div>`;
      return;
    }

    const rows = offers
      .map((o) => {
        const badges = [];
        if (o.is_cheapest) badges.push(`<span class="pill is-accent">Ən ucuz</span>`);
        if (o.is_best_value)
          badges.push(`<span class="pill is-green">Ən sərfəli</span>`);

        const unit = o.unit_price
          ? `<span class="cell-sub">1 ${esc(o.base_unit)} = ${money(o.unit_price)} ₼</span>`
          : "";

        const old = o.old_price
          ? `<span class="cell-sub old">${money(o.old_price)} ₼ ` +
            `(−${o.discount_pct.toFixed(0)}%)</span>`
          : "";

        // Ən ucuz sətir RƏNGLƏ deyil, ÇƏRÇİVƏ + ✓ ilə işarələnir: brend rəngi
        // artıq yaşıldır, ona görə yaşıl fon iki məna daşıyardı.
        const pill = o.is_cheapest
          ? `<span class="price-pill is-best">${icon("check")}` +
            `<span class="sr-only">Ən ucuz:</span>${price(o.price)}</span>`
          : `<span class="price-pill">${price(o.price)}</span>`;

        return (
          `<tr>` +
          `<td><div class="entity">${storeAvatar(o.store, "is-sm")}` +
          `<div class="entity-text"><div class="entity-name">${esc(o.store)}</div>` +
          `<div class="entity-meta">${badges.join(" ") || "&nbsp;"}</div></div></div></td>` +
          `<td class="num">${pill}${old}</td>` +
          `<td class="num txt">${unit || "—"}</td>` +
          `</tr>`
        );
      })
      .join("");

    const summary = compare
      ? `<div class="badges"><span class="badge ok">` +
        `Ən ucuz: <strong>${esc(compare.store)}</strong></span>` +
        `<span class="badge">Fərq: <strong>${money(compare.spread)} ₼</strong></span>` +
        `<span class="badge">${storeCountText(compare.stores)}</span></div>`
      : `<div class="badges"><span class="badge warn">` +
        `${storeCountText(offers.length)} — müqayisə üçün ikinci qiymət yoxdur</span></div>`;

    box.innerHTML =
      summary +
      `<div class="table-scroll"><table class="lines">` +
      `<thead><tr><th>Market</th><th class="num">Qiymət</th>` +
      `<th class="num">Vahid qiyməti</th></tr></thead>` +
      `<tbody>${rows}</tbody></table></div>`;
  }

  /**
   * Cədvəlin altındakı bir sətir: hansı marketin datası hələ yoxdur.
   *
   * Bu sətir olmasaydı, istifadəçi dörd market gözləyib iki görər və səbəbini
   * bilməzdi. «Tezliklə» isə vədin harada dayandığını açıq deyir.
   */
  function renderMarketNote(markets, offers) {
    const shown = new Set(offers.map((o) => o.store_slug));
    const soon = markets.filter((m) => !m.available).map((m) => m.name);
    const missing = markets
      .filter((m) => m.available && !shown.has(m.slug))
      .map((m) => m.name);

    const parts = [];
    if (missing.length)
      parts.push(`Bu məhsul ${missing.join(", ")} kataloqunda tapılmadı.`);
    if (soon.length) parts.push(`${soon.join(" və ")} — tezliklə.`);

    el("marketNote").textContent = parts.join(" ");
  }

  // ------------------------------------------------------------- variantlar

  function renderVariants(variants) {
    if (!variants.length) return;

    const rows = variants
      .map((v) => {
        const badges = [];
        if (v.is_cheapest) badges.push(`<span class="pill is-accent">Ən ucuz</span>`);
        if (v.is_best_value) badges.push(`<span class="pill is-green">Ən sərfəli</span>`);

        const unit = v.unit_price
          ? `1 ${esc(v.base_unit)} = ${money(v.unit_price)} ₼`
          : "—";

        // Cari məhsul öz sətrində link olmur - istifadəçi elə oradadır.
        const name = v.is_current
          ? `<strong>${esc(v.size)}</strong> <span class="cell-sub">bu səhifə</span>`
          : `<a class="link" href="/product/${v.product_id}">${esc(v.size)}</a>`;

        return (
          `<tr><td>${name}</td>` +
          `<td>${badges.join(" ") || "&nbsp;"}</td>` +
          `<td class="num">${price(v.price)}</td>` +
          `<td class="num txt">${unit}</td></tr>`
        );
      })
      .join("");

    el("variantsBox").innerHTML =
      `<div class="table-scroll"><table class="lines">` +
      `<thead><tr><th>Ölçü</th><th>Nişan</th><th class="num">Ən ucuz qiymət</th>` +
      `<th class="num">Vahid qiyməti</th></tr></thead>` +
      `<tbody>${rows}</tbody></table></div>`;
    el("variantsCard").classList.remove("hidden");
  }

  // -------------------------------------------------------- oxşar / brend

  function productCard(item) {
    const size = item.size ? `<span class="deal-size">${esc(item.size)}</span>` : "";
    return (
      `<a class="deal card-lift" href="/product/${item.product_id}">` +
      `<div class="deal-top">` +
      `<span class="avatar is-sm">${icon(categoryIcon(item.category))}</span>` +
      `</div>` +
      `<div class="deal-name">${esc(item.label)}</div>` +
      size +
      `<div class="deal-price"><span class="deal-now">${price(item.price)}</span></div>` +
      `<div class="deal-single">${storeCountText(item.store_count)}</div>` +
      `</a>`
    );
  }

  function renderGrid(items, boxId, cardId) {
    if (!items.length) return;
    el(boxId).innerHTML = items.map(productCard).join("");
    el(cardId).classList.remove("hidden");
  }

  // ---------------------------------------------------------------- AI qeydi

  async function loadNote() {
    try {
      const data = await (
        await fetch(`/api/catalog/product/${productId}/note`)
      ).json();

      // `available: false` - model əlçatmazdır, boş cavab verdi, uydurma rəqəm
      // yazdı və ya rəy ifadəsi işlətdi. Hər halda bölmə GÖSTƏRİLMİR.
      if (!data.available || !data.text) return;

      // Model mətni ETİBARSIZDIR: `textContent` ilə yazılır, yəni içindəki
      // hər hansı HTML sadəcə mətn kimi qalır.
      el("noteText").textContent = data.text;
      el("noteFacts").textContent = data.facts || "";
      el("noteCard").classList.remove("hidden");
    } catch (e) {
      console.error("[note]", e);
    }
  }

  el("noteFactsBtn").addEventListener("click", () => {
    const box = el("noteFacts");
    box.classList.toggle("hidden");
  });

  // ------------------------------------------------------------------ start

  async function load() {
    // İkonlar gəlməmiş render etsək, `<use>` istinadları boş qalardı.
    await window.IconsReady;

    let data;
    try {
      const res = await fetch(`/api/catalog/product/${productId}`);
      if (res.status === 404) {
        el("productHead").innerHTML =
          `<h1 class="page-title">Məhsul tapılmadı</h1>` +
          `<p class="page-sub">Link köhnəlmiş ola bilər. ` +
          `<a class="link" href="/">Ana səhifəyə qayıt</a>.</p>`;
        el("offersBox").innerHTML = "";
        return;
      }
      data = await res.json();
    } catch (e) {
      console.error("[product]", e);
      el("offersBox").innerHTML =
        `<div class="notice error">Məhsul datası yüklənmədi.</div>`;
      return;
    }

    const offers = data.offers || [];
    // Market rəngləri render başlamazdan ƏVVƏL elan olunur (bax store-colors.js).
    StoreColors.note([
      ...(data.markets || []).map((m) => m.name),
      ...offers.map((o) => o.store),
    ]);

    renderHead(data.product, offers);
    renderOffers(offers, data.compare);
    renderMarketNote(data.markets || [], offers);
    renderVariants(data.variants || []);
    renderGrid(data.similar || [], "similarBox", "similarCard");
    renderGrid(data.same_brand || [], "brandBox", "brandCard");

    loadNote();
  }

  load();
})();
