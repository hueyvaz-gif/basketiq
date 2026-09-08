// «Bugünün ən sərfəli endirimləri» — ana səhifədəki kəşf bölməsi.
//
// NƏ GÖSTƏRİLİR VƏ NƏ GÖSTƏRİLMİR?
// Kartın böyük rəqəmi ENDİRİM FAİZİDİR, çünki bölmənin sualı budur:
// «bu gün nə ucuzlayıb?». Amma faiz tək başına aldadıcıdır — 50% endirim
// qonşu marketin adi qiymətindən baha ola bilər. Ona görə hər kartın altında
// həmin məhsulun DİGƏR marketlərdəki qiyməti də var.
//
// Məhsul yalnız bir marketdə varsa, boş sətir və ya «—» YAZILMIR: bir sətirlə
// «yalnız filan marketdə tapılıb» yazılır. Boş xana istifadəçiyə "qiymət
// sıfırdır" və ya "səhv var" kimi görünür; açıq cümlə isə məlumatdır.

(() => {
  const grid = document.getElementById("dealsGrid");
  const moreBtn = document.getElementById("dealsMore");

  // İlk baxışda 8 kart: bölmə səhifəni udmamalıdır. «Daha çox» ilə açılır.
  const FIRST = 8;
  const MORE = 24;
  let shown = FIRST;

  /** Kartın altındakı market müqayisəsi. */
  function offersBlock(deal) {
    const offers = deal.offers || [];
    if (offers.length < 2) {
      const only = offers[0]?.store || deal.store;
      return `<div class="deal-single">Yalnız ${esc(only)}-də tapılıb</div>`;
    }

    const rows = offers
      .map(
        (o) =>
          `<div class="deal-offer${o.is_cheapest ? " is-best" : ""}">` +
          `<span class="deal-offer-store">${storeAvatar(o.store, "is-xs")}` +
          `${esc(o.store_short)}</span>` +
          `<span class="deal-offer-price">${price(o.price)}</span></div>`
      )
      .join("");

    return `<div class="deal-offers">${rows}</div>`;
  }

  function card(deal) {
    // Faiz nişanı MƏTNLƏ də oxunur: rəngi görməyən istifadəçi üçün
    // «-52%» yazısının özü siqnaldır.
    const pct = `<span class="deal-pct">−${deal.discount_pct.toFixed(0)}%</span>`;
    const size = deal.size
      ? `<span class="deal-size">${esc(deal.size)}</span>`
      : "";

    return (
      `<a class="deal card-lift" href="/product/${deal.product_id}">` +
      `<div class="deal-top">` +
      `<span class="avatar is-sm">${icon(categoryIcon(deal.category))}</span>` +
      pct +
      `</div>` +
      `<div class="deal-name">${esc(deal.label)}</div>` +
      size +
      `<div class="deal-price">` +
      `<span class="deal-now">${price(deal.price)}</span>` +
      `<span class="deal-was">${price(deal.old_price)}</span>` +
      `</div>` +
      `<div class="deal-store">${storeChip(deal.store)}</div>` +
      offersBlock(deal) +
      `</a>`
    );
  }

  function renderDeals(items) {
    if (!items.length) {
      grid.innerHTML =
        `<div class="notice warn">Hazırda endirimli məhsul tapılmadı. ` +
        `Admin panelindən kataloq yükləyin — endirimlər həmin kataloqdan çıxarılır.</div>`;
      moreBtn.classList.add("hidden");
      return;
    }
    // Rəngləri əvvəlcədən elan edirik ki, kartlar çəkilərkən market rəngi
    // dəyişməsin (bax `store-colors.js`).
    StoreColors.note(items.flatMap((d) => (d.offers || []).map((o) => o.store)));
    grid.innerHTML = items.map(card).join("");
  }

  async function load(limit) {
    try {
      const deals = await (
        await fetch(`/api/catalog/deals?limit=${limit}`)
      ).json();

      renderDeals(deals.items || []);

      // Düymə yalnız İLK vəziyyətdə və hər şey onsuz da sığırsa gizlənir.
      // Açıq vəziyyətdə gizlətsək, istifadəçi siyahını yığa bilməzdi.
      const total = deals.total_found || 0;
      const fitsAtOnce = shown === FIRST && (deals.items || []).length >= total;
      moreBtn.classList.toggle("hidden", fitsAtOnce);
    } catch (e) {
      // Bölmə səhifənin qalanını dayandırmamalıdır.
      console.error("[deals]", e);
      grid.innerHTML =
        `<div class="notice warn">Endirim siyahısı yüklənmədi. ` +
        `Səhifənin qalan hissəsi işləyir.</div>`;
      moreBtn.classList.add("hidden");
    }
  }

  moreBtn.addEventListener("click", () => {
    shown = shown === FIRST ? MORE : FIRST;
    moreBtn.textContent = shown === FIRST ? "Daha çox göstər" : "Daha az göstər";
    load(shown);
  });

  load(shown);
})();
