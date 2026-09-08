// «Bugünün ən sərfəli endirimləri» — trolley üslubunda NÖMRƏLƏNMİŞ SİYAHI.
//
// NİYƏ KART ŞƏBƏKƏSİ DEYİL, SİYAHI?
// İlk variant kiçik kartlar şəbəkəsi idi. Trolley-nin öz səhifəsinə baxdıq:
// orada endirimlər ALT-ALTA sıralanır, hər sətirdə solda böyük məhsul şəkli,
// sağda isə ad, ölçü və MARKETLƏRİN QİYMƏTLƏRİ yan-yana durur. Səbəb aydındır:
// bu bölmənin məzmunu bir rəqəm deyil, MÜQAYİSƏDİR - müqayisə isə enə ehtiyac
// duyur. Kiçik kartda üç marketin qiyməti yan-yana sığmır.
//
// SIRA NÖMRƏSİ (1, 2, 3…) təsadüfi bəzək deyil: siyahı ən böyük endirimdən
// başlayır və nömrə bunu göz üçün təsdiqləyir.
//
// ŞƏKİL: `products.image_path` kataloq səhifəsindən kəsilir
// (`ingestion/images.py`). Şəkli olmayan məhsul neytral placeholder alır -
// uydurma foto qoyulmur.

(() => {
  const grid = document.getElementById("dealsGrid");
  const moreBtn = document.getElementById("dealsMore");

  const FIRST = 6;
  const MORE = 24;
  let shown = FIRST;

  // slug -> loqo ünvanı. Market qiymət sütunlarında marketin ADI yox,
  // LOQOSU görünür (trolley də belədir) - loqo daha tez tanınır.
  let logos = new Map();

  /** Marketin qiymət sütunu: loqo (və ya ad) + qiymət. */
  function storeColumn(offer) {
    const logo = logos.get(offer.store_slug);
    const mark = logo
      ? `<img class="pricecol-logo" src="${esc(logo)}" alt="${esc(offer.store)}">`
      : `<span class="pricecol-name">${esc(offer.store_short)}</span>`;

    return (
      `<div class="pricecol${offer.is_cheapest ? " is-best" : ""}">` +
      mark +
      `<span class="pricecol-price">${price(offer.price)}</span>` +
      `</div>`
    );
  }

  function row(deal, rank) {
    const offers = deal.offers || [];
    const size = deal.size ? `<span class="size-pill">${esc(deal.size)}</span>` : "";
    const brand = deal.brand
      ? `<div class="deal-brand">${esc(deal.brand)}</div>`
      : "";

    // Ad brenddən ayrı yazılır: trolley-də brend qalın, ad isə onun altında
    // adi çəkidədir - göz əvvəlcə brendi tutur.
    const title = esc(deal.label.replace(deal.brand ? deal.brand + " " : "", ""));

    const stores = offers.length
      ? `<div class="pricecols">${offers.map(storeColumn).join("")}</div>`
      : `<div class="deal-single">Yalnız ${esc(deal.store)}-də tapılıb</div>`;

    return (
      `<a class="deal-row" href="/product/${deal.product_id}">` +
      `<span class="deal-rank">${rank}</span>` +
      `<span class="deal-photo">` +
      `<img src="${esc(deal.image)}" alt="" loading="lazy">` +
      `<span class="deal-flag">−${deal.discount_pct.toFixed(0)}%</span>` +
      `</span>` +
      `<span class="deal-body">` +
      brand +
      `<span class="deal-title">${title}</span>` +
      `<span class="deal-meta">${size}` +
      `<span class="deal-save">${money(deal.saving)} ₼ qənaət</span></span>` +
      `<span class="deal-avail">Mövcuddur</span>` +
      stores +
      `</span>` +
      `</a>`
    );
  }

  function render(items) {
    if (!items.length) {
      grid.innerHTML =
        `<div class="notice warn">Hazırda endirimli məhsul tapılmadı. ` +
        `Admin panelindən kataloq yükləyin.</div>`;
      moreBtn.classList.add("hidden");
      return;
    }
    StoreColors.note(items.flatMap((d) => (d.offers || []).map((o) => o.store)));
    grid.innerHTML = items.map((deal, i) => row(deal, i + 1)).join("");
  }

  async function load(limit) {
    try {
      const [deals, markets] = await Promise.all([
        fetch(`/api/catalog/deals?limit=${limit}`).then((r) => r.json()),
        fetch("/api/catalog/markets").then((r) => r.json()),
      ]);

      logos = new Map(
        (markets.items || []).filter((m) => m.logo).map((m) => [m.slug, m.logo])
      );
      render(deals.items || []);

      const total = deals.total_found || 0;
      const fitsAtOnce = shown === FIRST && (deals.items || []).length >= total;
      moreBtn.classList.toggle("hidden", fitsAtOnce);
    } catch (e) {
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
