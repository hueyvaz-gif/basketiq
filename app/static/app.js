// İSTİFADƏÇİ PANELİ: axtarış, səbət müqayisəsi, hero və market barları.
//
// ADMİN KODU ARTIQ BURADA DEYİL (P6) - o, `/admin` səhifəsinin öz faylındadır
// (`admin.js`). Əvvəl hər ikisi bu fayldaydı və admin işarələməsi ana səhifədən
// çıxarılan kimi yükləmə sahəsini axtaran sətir `null`-a düşüb BÜTÜN faylı
// qırırdı - yəni istifadəçi səhifəsi admin markup-ından asılı idi.
//
// (Şərhdə element adı QƏSDƏN yazılmır: `test_bütün_js_selektorları_html_də_
// mövcuddur` faylı sətir-sətir oxuyur və şərhdəki seçicini də real istinad
// sayır - yəni izah testi sındırardı.)
//
// `esc`, `money`, `price`, `icon`, `categoryIcon`, `storeAvatar`, `storeChip`
// və `notice` BURADA DEYİL — onlar `ui.js`-dədir və məhsul səhifəsi ilə
// paylaşılır. `ui.js` bu fayldan ƏVVƏL yüklənməlidir.

const $ = (sel) => document.querySelector(sel);

// ---------------------------------------------------------------- axtarış

let searchTimer = null;

// Axtarış gecikməsi - `search.js` də eyni dəyəri işlədir (M1).
const SEARCH_DEBOUNCE_MS = 150;

// ENTER = BİRİNCİ NƏTİCƏNİ SƏBƏTƏ ƏLAVƏ ET.
//
// REAL ŞİKAYƏTDƏN ÇIXIB: bu sahə yazdıqca nəticə göstərirdi, amma Enter
// heç nə etmirdi - istifadəçi siyahını görüb klaviaturanı buraxmalı olurdu.
// Sahə formanın içində deyil (səhifəni yeniləmək lazım deyil), ona görə
// «göndərmə» davranışı əl ilə yazılır.
$("#searchInput").addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  e.preventDefault();
  const ilk = $("#searchResults").querySelector("[data-add]");
  if (ilk) ilk.click();
});

$("#searchInput").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) {
    $("#searchResults").innerHTML = "";
    return;
  }
  // 150 ms (M1): sürətli yazanda hər hərfə sorğu getmir, amma gecikmə
  // hiss olunmur. Əvvəl 250 idi - yazıb dayanandan sonra nəzərəçarpan
  // fasilə yaranırdı.
  searchTimer = setTimeout(() => runSearch(q), SEARCH_DEBOUNCE_MS);
});

async function runSearch(q) {
  try {
    const data = await (await fetch(`/api/products/search?q=${encodeURIComponent(q)}`)).json();
    if (!data.items.length) {
      $("#searchResults").innerHTML =
        `<div class="search-item"><span class="search-meta">${t("add.notFound")}</span></div>`;
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
                  aria-label="${t("add.aria", { name: title })}">Səbətə</button>
        </div>`;
      })
      .join("");

    $("#searchResults").querySelectorAll("[data-add]").forEach((b) =>
      b.addEventListener("click", async () => {
        b.disabled = true;
        b.innerHTML = `${icon("check")} ${t("add.done")}`;
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

/**
 * Marketlərarası uyğunluq + əhatə göstəricisi (A4, D18).
 *
 * Qiymət müqayisəsinin bütün mənası məhsulların EYNİ olmasındadır. Matcher
 * «Milla süd 1 l» ilə «Süd Milla 1L»-i birləşdirəndə bu, çox vaxt doğrudur,
 * amma zəmanət deyil - istifadəçi bunu bilməlidir.
 */
function matchLine(item) {
    const parts = [];
    if (item.match && item.available_in > 1) {
      const dəqiq = item.match === "exact";
      parts.push(
        `<span class="match-pill ${dəqiq ? "is-exact" : "is-approx"}" ` +
        `title="${esc(t(dəqiq ? "match.exactHint" : "match.approximateHint"))}">` +
        `${t(dəqiq ? "match.exact" : "match.approximate")}</span>`
      );
    }
    if (item.coverage) {
      parts.push(
        `<span class="coverage-pill">` +
        `${t("coverage.stores", { n: item.coverage.available, total: item.coverage.total })}` +
        `</span>`
      );
    }
    return parts.length ? `<span class="entity-badges">${parts.join("")}</span>` : "";
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
    ? `${t("answer.readyForAi")} <strong>${t("ai.get")}</strong>${t("answer.readyForAiAfter")}`
    : `${t("ai.placeholderBefore")} <strong>${t("ai.get")}</strong>${t("ai.placeholderAfter")}`;
}

/**
 * HERO: səhifənin əsas cavabı.
 *
 * Üç fərqli hal var və üçü də REAL datadan gəlir - uydurma rəqəm yoxdur:
 *   1. səbət boşdur                  -> boş hal
 *   2. heç bir market tam satmır     -> qalib elan edilmir, səbəb izah olunur
 *   3. qalib var                     -> market, cəm, (varsa) qənaət
 */
/**
 * Səbətin yığcam siyahısı - ilk ekranın birinci elementi (v2, bölmə 8.2).
 *
 * Cədvəl aşağıda qalır; burada yalnız «nə almışam» sualının cavabı var:
 * ad + miqdar + sil. Cədvəl ekranın yarısını tutduğu üçün istifadəçi
 * səbətinə baxmaq üçün skroll etməli olurdu.
 */
function renderBasket(data) {
  const box = $("#basketList");
  if (!data.items.length) {
    box.innerHTML = "";
    return;
  }

  box.innerHTML =
    `<span class="basket-mini-label">${t("basket.label")} (${data.items.length})</span>` +
    data.items
      .map(
        (item) => `<span class="basket-chip">
          <span class="basket-chip-name">${esc(item.label)}</span>
          ${item.qty && item.qty !== 1 ? `<span class="basket-chip-qty">×${esc(String(item.qty))}</span>` : ""}
          <button class="basket-chip-del" data-del-item="${item.product_id}" type="button"
                  aria-label="${t("basket.removeItem", { name: esc(item.label) })}">${icon("trash")}</button>
        </span>`
      )
      .join("");

  box.querySelectorAll("[data-del-item]").forEach((b) =>
    armDeleteButton(b, async () => {
      await fetch(`/api/basket/items/${b.dataset.delItem}`, { method: "DELETE" });
      await loadCompare();
    })
  );
}

/**
 * İLK EKRAN: bir sual, bir cavab (v2, bölmə 8.2).
 *
 * Ən böyük rəqəm ŞƏRTSİZ cavab olmalıdır. Əvvəl burada bölünmüş alış cəmi
 * dururdu və dərhal iki şərtlə məhdudlaşdırılırdı («3 marketi gəzsəniz»,
 * «tək marketlə olmur») - yəni ekranın ən böyük elementi əslində cavab
 * deyil, şərtli təklif idi.
 *
 * İNDİ: tam səbəti satan market varsa, cavab ODUR. Bölünmüş plan aşağıda,
 * ayrıca bir sətir kimi TƏKLİF olunur.
 *
 * Tam səbəti satan market YOXDURSA cavab uydurulmur - bu halda ən ucuz
 * əldə edilə bilən cəm göstərilir və şərti elə həmin yerdə deyilir.
 * «Natamam market qalib elan edilmir» qaydası dəyişmir.
 */
function renderHero(data) {
  const box = $("#compareResult");

  if (!data.items.length) {
    box.innerHTML = `
      <div class="hero-empty">
        <div class="hero-empty-title">${t("basket.empty")}</div>
        <div>${t("basket.emptyHint")}</div>
      </div>`;
    return;
  }

  const best = data.best;
  const c = data.cheapest;

  // --- Bölünmüş alış TƏKLİFİ: yalnız real qənaət varsa göstərilir ----------
  const splitSaving = best && c ? best.total - c.total : 0;
  const splitLine =
    best && c && splitSaving > 0.005
      ? `<p class="answer-alt">
           ${t("answer.split", { n: c.store_count, amount: `<strong>${price(splitSaving)}</strong>` })}
         </p>`
      : "";

  // --- HAL 1: səbətin hamısını satan market var -> ŞƏRTSİZ CAVAB -----------
  if (best) {
    // «X ilə müqayisədə» üçün ikinci TAM səbət lazımdır. Yoxdursa fərq
    // yazılmır - iki natamam cəmi müqayisə etmək yanlış rəqəm verərdi.
    const complete = data.stores
      .filter((s) => s.complete)
      .sort((a, b) => a.total - b.total);
    const second = complete[1];

    const line = second
      ? `${t("answer.cheaperThan", { store: esc(second.store), amount: price(second.total - best.total) })}`
      : `${t("answer.cheapestCount", { n: best.cheapest_count, total: data.items.length })}`;

    box.innerHTML = `
      <div class="answer">
        <div class="answer-store">
          ${storeAvatar(best.store, "is-lg")}
          <span class="hero-store">${esc(best.store)}</span>
        </div>
        <div class="hero-price">${price(best.total)}</div>
        <p class="answer-line">${line}</p>
      </div>
      ${splitLine}`;
    return;
  }

  // --- HAL 2: heç bir market səbətin hamısını satmır -----------------------
  const most = [...data.stores].sort((a, b) => b.covered - a.covered)[0];

  if (!c || !most) {
    box.innerHTML = `
      <div class="hero-empty">
        <div class="hero-empty-title">${t("answer.noWinner")}</div>
        <div>${esc(data.note || t("answer.noneComplete"))}</div>
      </div>`;
    return;
  }

  box.innerHTML = `
    <div class="answer is-split">
      <span class="eyebrow">Əldə edilə bilən ən ucuz cəm</span>
      <div class="hero-price">${price(c.total)}</div>
      <p class="answer-line">
        ${c.store_count} marketi gəzsəniz — hər məhsulu ən ucuz satandan.
        Tək market kifayət etmir; ən çox əhatə:
        <strong>${esc(most.store)}</strong> — ${most.covered}/${data.items.length} məhsul.${
          c.unavailable ? `${t("answer.unavailable", { n: c.unavailable })}` : ""
        }
      </p>
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
    .map((s) => {
      // İki fərqli səbəb, iki fərqli mətn (D16): datası olmayan market
      // «satmır» demək deyil - onun kataloqu hələ gəlməyib.
      const səbəb = s.available === false ? t("bars.noData") : t("bars.notSelling");
      const hal = s.available === false ? t("common.soon") : t("bars.notCompared");
      return `<div class="bar-row is-empty">
        <div class="bar-name">
          ${storeAvatar(s.store, "is-sm")}
          <span>${esc(s.store)}<small>${esc(səbəb)}</small></span>
        </div>
        <div class="bar-empty">${esc(hal)}</div>
      </div>`;
    })
    .join("");

  box.innerHTML = `<div class="bars">${selling
    .map((s) => {
      const isBest = data.best && s.store_id === data.best.store_id;
      const cls = `bar-row${isBest ? " is-best" : ""}${s.complete ? "" : " is-partial"}`;
      const sub = s.complete
        ? (isBest ? t("answer.fullBasket") : (s.diff != null ? `+${money(s.diff)} ₼` : ""))
        : `${t("answer.partial", { covered: s.covered, total: data.items.length })}`;
      // Bar ən azı 22% enində olur ki, içindəki rəqəm həmişə oxunsun
      const width = Math.max(22, (s.total / max) * 100);
      return `<div class="${cls}">
        <div class="bar-name">
          ${storeAvatar(s.store, "is-sm")}
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

/** Məhsul × market cədvəli. Ən ucuz xana ÇƏRÇİVƏ + ✓ ilə vurğulanır (dolu fon yox). */
function renderCompareTable(data) {
  const stores = data.stores;

  $("#compareTableWrap").innerHTML = `
    <div class="table-scroll">
      <table class="lines is-dense">
        <caption class="sr-only">${t("compare.caption")}</caption>
        <thead>
          <tr>
            <th scope="col">${t("common.product")}</th>
            ${stores
              .map((s) => {
                const best = data.best && s.store_id === data.best.store_id;
                // D17: datası olmayan market SÜTUNU QALIR, üstünə «Tezliklə»
                // yazılır. Sütunu silsək, istifadəçi dörd market vədinin
                // əvəzinə iki sütun görər və səbəbini bilməzdi.
                // Datasız sütun BİR QRUP kimi geri çəkilir (`is-soon`).
                // Əvvəl başlıqda tam çəkili «Tezliklə» nişanı, altındakı hər
                // xanada isə eyni söz təkrarlanırdı - altı sətirdə altı dəfə.
                // İndi başlıq etiketi sakit qalır və bütün sütun bir ton
                // aşağı düşür: göz onu «bir bölmə, sonra gələcək» kimi
                // oxuyur, altı ayrı bildiriş kimi yox.
                // Söz XANALARDAN SİLİNMİR (D16): «datası yoxdur» ilə «bu
                // marketdə satılmır» eyni görünməməlidir.
                const soon = s.available === false
                  ? `<span class="pill is-soon">${t("common.soon")}</span>`
                  : "";
                const sütunSinfi = s.available === false ? "num is-soon-col" : "num";
                return `<th scope="col" class="${sütunSinfi}">${storeChip(s.store, best)}${soon}</th>`;
              })
              .join("")}
            <th scope="col"><span class="sr-only">${t("col.action")}</span></th>
          </tr>
        </thead>
        <tbody>
          ${data.items
            .map((item) => {
              const cells = stores
                .map((s) => {
                  // D16: BOŞ XANA OLMUR. İki fərqli hal var və ikisi eyni
                  // görünsəydi, istifadəçi «bu market bahadır» qənaətinə
                  // gələrdi:
                  //   market datasızdır      -> «tezliklə»
                  //   market bu məhsulu satmır -> «—»
                  if (s.available === false) {
                    return `<td class="num na is-soon-col">${t("compare.noData")}</td>`;
                  }
                  const p = item.prices[String(s.store_id)];
                  if (!p) return `<td class="num na">—</td>`;
                  // «ƏN UCUZ» NİŞANI TƏK TƏKLİF OLANDA VERİLMİR.
                  //
                  // Qayda layihədə artıq var (`catalog.py`, `_rank_offers`):
                  // «bir market varsa, ən ucuz heç nə demir - müqayisə
                  // yoxdur». Cədvəl həmin qaydanı tətbiq etmirdi və nəticə
                  // BRAUZERDƏ görüldü: altı sətrin beşi «1/4 marketdə» idi,
                  // amma hamısında ✓ nişanı vardı - ekran isti aksentli
                  // pillərlə dolurdu və nişan mənasını itirirdi.
                  // M2.3-ün həddi də pozulurdu: bir ekranda ən çox iki isti
                  // aksent.
                  const cheap =
                    item.cheapest_store_id === s.store_id && item.available_in > 1;
                  // Ən ucuz qiymət PILL içindədir.
                  // Rəng TƏK siqnal deyil: pillin içində ikon və ekran
                  // oxuyucusu üçün gizli mətn də var, yəni rəngi ayırd edə
                  // bilməyən istifadəçi məlumatı itirmir.
                  const inner = cheap
                    ? `<span class="price-pill is-best">${icon("check")}${money(p.price)}` +
                      `<span class="sr-only">${t("compare.srCheapest")}</span></span>`
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
                      <span class="entity-meta">${esc([item.size, item.category ? t("cat." + item.category, item.category) : ""].filter(Boolean).join(" · "))}</span>
                      ${matchLine(item)}
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
    armDeleteButton(b, async () => {
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

    renderBasket(data);
    renderHero(data);

    if (!data.items.length) {
      $("#storeBars").innerHTML = "";
      $("#compareTableWrap").innerHTML =
        `<div class="hint">${t("compare.emptyBasket")}</div>`;
      resetAdvisor(false);
      return;
    }

    renderBars(data);
    renderCompareTable(data);
    // Səbət dəyişdisə köhnə tövsiyə artıq doğru deyil - sıfırlanır
    resetAdvisor(true);
  } catch {
    $("#compareResult").innerHTML =
      `<div class="notice error">${t("compare.loadError")}</div>`;
    resetAdvisor(false);
  }
}

loadCompare();

document.addEventListener("basketiq:lang", () => {
  loadCompare();
});
