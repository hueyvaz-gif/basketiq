// SƏBƏT SƏHİFƏSİ — səbətin içi, market üzrə cəm və tövsiyə olunan plan.
//
// ÜÇ BÖLMƏ, BİR MƏNBƏ. Hər üçü eyni sorğu dəstindən qidalanır və hər
// dəyişiklikdən sonra ÜÇÜ DƏ yenidən çəkilir. Səbəb: səbətdən bir məhsul
// silinəndə plan da, cəmlər də dəyişir - biri köhnə qalsa, ekranda iki
// fərqli həqiqət olardı.
//
// «MƏLUMAT YOXDUR» İLƏ «BAHALIDIR» FƏRQLƏNİR. Datası olmayan market
// silinmir: sətri qalır və səbəbi yazılır. Gizlətsək, istifadəçi dörd
// market vədinin əvəzinə iki sətir görər və səbəbini bilməz.

(() => {
  const itemsBox = document.getElementById("basketItems");
  const totalsBox = document.getElementById("basketTotals");
  const planBox = document.getElementById("basketPlan");
  if (!itemsBox) return;

  const skelet = (hündürlük = 60) =>
    `<div class="skeleton-row" style="height:${hündürlük}px"></div>`;

  // ------------------------------------------------------------ səbətin içi

  function itemRow(item) {
    const ölçü = item.size_value
      ? `<span class="size-pill">${esc(item.size_value)} ${esc(item.size_unit || "")}</span>`
      : "";
    const ad = [item.brand, item.name].filter(Boolean).join(" ");

    return `<div class="basket-row" data-product="${item.product_id}">
        <a class="basket-name" href="/product/${item.product_id}">
          <span class="thumb is-cat ${esc(catTone(item.category))}">${icon(categoryIcon(item.category))}</span>
          <span>
            <strong>${esc(ad)}</strong>
            <span class="row-note">${ölçü}${esc(t("cat." + item.category, item.category || ""))}</span>
          </span>
        </a>
        <span class="qty">
          <button class="icon-btn is-sm" type="button" data-qty="${item.product_id}" data-delta="-1"
                  aria-label="${esc(t("basket.less"))}">−</button>
          <span class="qty-value">${item.qty}</span>
          <button class="icon-btn is-sm" type="button" data-qty="${item.product_id}" data-delta="1"
                  aria-label="${esc(t("basket.more"))}">+</button>
        </span>
        <button class="icon-btn" type="button" data-del-item="${item.product_id}"
                aria-label="${esc(ad)}">${icon("trash")}</button>
      </div>`;
  }

  const catTone = (category) => {
    const ikon = categoryIcon(category);
    return ikon === "package" ? "is-cat-other" : `is-${ikon}`;
  };

  // ------------------------------------------------------- market üzrə cəm

  function totalsRow(store, best) {
    // ÜÇ FƏRQLİ HAL, ÜÇ FƏRQLİ MƏTN:
    //   datası yoxdur        -> «bu marketdə qiymət yoxdur»
    //   bəzi məhsulu satmır  -> «N məhsul yoxdur», cəm göstərilmir
    //   hamısını satır       -> cəm və ən ucuzdan fərq
    if (store.available === false) {
      return `<div class="row is-muted">
          <span class="row-label">${storeAvatar(store.store, "is-sm")}${esc(store.store)}</span>
          <span class="row-value is-quiet">${esc(t("basket.noData"))}</span>
        </div>`;
    }

    if (!store.complete) {
      return `<div class="row is-muted">
          <span class="row-label">${storeAvatar(store.store, "is-sm")}${esc(store.store)}
            <span class="row-note">${esc(t("basket.missingN", { n: store.missing.length }))}</span>
          </span>
          <span class="row-value is-quiet">${esc(t("basket.notCompared"))}</span>
        </div>`;
    }

    const ucuz = best && store.store_id === best.store_id;
    const fərq =
      !ucuz && store.diff != null
        ? `<span class="row-note">+${money(store.diff)} ₼</span>`
        : "";

    return `<div class="row${ucuz ? " is-best" : ""}">
        <span class="row-label">${storeAvatar(store.store, "is-sm")}${esc(store.store)}
          ${ucuz ? `<span class="pill is-accent">${icon("check")}${esc(t("basket.cheapest"))}</span>` : ""}
        </span>
        <span class="row-value">${price(store.total)} ${fərq}</span>
      </div>`;
  }

  // -------------------------------------------------------------------- plan

  function planView(plan, compare) {
    if (plan.plan === "yoxdur") {
      return `<div class="notice">${esc(plan.notes[0] || t("basket.noPlan"))}</div>`;
    }

    const tək = plan.plan === "tek_market";
    const başlıq = tək
      ? t("basket.planSingle", { store: plan.stores[0] || "" })
      : t("basket.planSplit", { n: plan.stores.length });

    // QƏNAƏT YALNIZ REAL OLANDA YAZILIR.
    //
    // İki şərt: hər iki rəqəm mövcuddur VƏ fərq sıfırdan böyükdür. «0.00 ₼
    // qənaət» sətri heç nə demir - üstəlik istifadəçini «deməli bölmək də
    // olar» fikrinə salır. Səbəbi (niyə bölmək sərfəli deyil) planın öz
    // qeydlərində yazılır.
    const fərq =
      plan.single_total != null && plan.split_total != null
        ? plan.single_total - plan.split_total
        : 0;
    const qənaət =
      fərq > 0.005
        ? `<div class="row">
             <span class="row-label">${esc(t("basket.splitSaving", { n: plan.stores.length > 1 ? plan.stores.length : 2 }))}</span>
             <span class="row-value">${money(fərq)} ₼</span>
           </div>`
        : "";

    const sətirlər = (plan.assignments || [])
      .map((a) => {
        // Heç bir marketdə tapılmayan məhsul planı POZMUR: ayrıca yazılır.
        if (!a.store) {
          return `<div class="row is-muted">
              <span class="row-label">${esc(a.label)}</span>
              <span class="row-value is-quiet">${esc(t("basket.noPriceAnywhere"))}</span>
            </div>`;
        }
        return `<div class="row">
            <span class="row-label">${esc(a.label)}</span>
            <span class="row-value">${storeAvatar(a.store, "is-xs")}${esc(a.store)} · ${price(a.price)}</span>
          </div>`;
      })
      .join("");

    const xəbərdarlıq = (plan.warnings || [])
      .map((w) => `<div class="notice warn">${esc(w)}</div>`)
      .join("");

    // PLANIN SƏBƏBİ göstərilir: «niyə tək market?», «niyə bölünmüş?».
    // Rəqəm tövsiyəni izah etmir - izahı `app/recommend.py` onsuz da
    // hesablayır, sadəcə ekrana çıxmırdı.
    const səbəb = (plan.notes || [])
      .map((n) => `<p class="plan-note">${esc(n)}</p>`)
      .join("");

    return `<div class="plan-head">
        <span class="plan-kind">${esc(başlıq)}</span>
        <span class="plan-total">${price(plan.total)}</span>
      </div>
      ${qənaət}
      <div class="plan-lines">${sətirlər}</div>
      ${səbəb}
      ${xəbərdarlıq}
      ${
        compare.cheapest && compare.cheapest.unavailable
          ? `<div class="notice warn">${esc(
              t("basket.someUnavailable", { n: compare.cheapest.unavailable })
            )}</div>`
          : ""
      }`;
  }

  // ------------------------------------------------------------------ yükləmə

  async function load() {
    // SKELET, AĞ EKRAN YOX: sorğular paralel gedir, amma cavab gələnə qədər
    // bölmələrin forması görünür - səhifə «sındı» kimi oxunmur.
    itemsBox.innerHTML = skelet(64) + skelet(64);
    totalsBox.innerHTML = skelet(48) + skelet(48);
    planBox.innerHTML = skelet(96);

    let basket, compare, plan;
    try {
      [basket, compare, plan] = await Promise.all([
        fetch("/api/basket").then((r) => r.json()),
        fetch("/api/basket/compare").then((r) => r.json()),
        fetch("/api/profile/recommend").then((r) => r.json()),
      ]);
    } catch {
      itemsBox.innerHTML = `<div class="notice error">${esc(t("basket.loadError"))}</div>`;
      return;
    }

    const items = basket.items || [];
    if (!items.length) {
      itemsBox.innerHTML = `<div class="hero-empty">
          <div class="hero-empty-title">${esc(t("basket.empty"))}</div>
          <div>${esc(t("basket.emptyHint"))}</div>
          <a class="btn" href="/search">${esc(t("basket.goSearch"))}</a>
        </div>`;
      totalsBox.innerHTML = `<div class="notice">${esc(t("basket.emptyTotals"))}</div>`;
      planBox.innerHTML = `<div class="notice">${esc(t("basket.emptyPlan"))}</div>`;
      return;
    }

    itemsBox.innerHTML = items.map(itemRow).join("");
    totalsBox.innerHTML = (compare.stores || []).map((s) => totalsRow(s, compare.best)).join("");
    planBox.innerHTML = planView(plan, compare);

    wire();
  }

  function wire() {
    for (const btn of itemsBox.querySelectorAll("[data-qty]")) {
      btn.addEventListener("click", async () => {
        const sətir = btn.closest(".basket-row");
        const cari = Number(sətir.querySelector(".qty-value").textContent);
        const yeni = cari + Number(btn.dataset.delta);
        btn.disabled = true;

        // Sıfıra düşən miqdar SİLMƏ deyil: istifadəçi «−» düyməsini bir dəfə
        // artıq basanda məhsulun yox olması gözlənilməzdir. Ən aşağı hədd 1-dir,
        // silmək üçün ayrıca düymə var (təsdiqli).
        if (yeni < 1) {
          btn.disabled = false;
          return;
        }
        await fetch("/api/basket/items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_id: Number(btn.dataset.qty), qty: yeni }),
        });
        document.dispatchEvent(new CustomEvent("basketiq:basket"));
        load();
      });
    }

    // Silmə TƏSDİQİN arxasındadır - layihənin ümumi qaydası (`app.js`).
    for (const btn of itemsBox.querySelectorAll("[data-del-item]")) {
      armDeleteButton(btn, async () => {
        await fetch(`/api/basket/items/${btn.dataset.delItem}`, { method: "DELETE" });
        document.dispatchEvent(new CustomEvent("basketiq:basket"));
        load();
      });
    }
  }

  load();
  document.addEventListener("basketiq:lang", load);
})();
