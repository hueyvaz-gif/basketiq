// Ana səhifədəki MARKET ŞƏBƏKƏSİ — trolley-nin mağaza şəbəkəsinin qarşılığı.
//
// Kartın quruluşu qəsdən sadədir: düz künc, ağ fon, nazik boz kənar, mərkəzdə
// loqo. Loqo kartın YEGANƏ məzmunudur, çünki markanı tanıdan da odur — ad
// yazısı loqonun altında ancaq dəstəkdir.
//
// LOQO FAYLI OLMAYA BİLƏR.
// Fayllar `app/static/images/` qovluğuna əl ilə qoyulur (araz.png, bravo.png,
// bazar.png, rahat.png). Fayl yoxdursa kart SINMIR: şəkil silinir və yerinə
// marketin adı böyük hərflərlə yazılır. Uydurma loqo çəkmirik - saxta brend
// nişanı istifadəçini yanıldar.
//
// «TEZLİKLƏ» NƏDİR?
// Bazar Store və Rahat Market üçün hələ data mənbəyi yoxdur. Kartları
// siyahıdan çıxarmırıq (istifadəçiyə dörd market vəd olunub), amma vəziyyəti
// gizlətmirik də: kart kəsik çərçivə ilə çəkilir və «Tezliklə» yazılır.
// Kart yenə də kliklənir - marketin səhifəsi vəziyyəti izah edir.

(() => {
  const grid = document.getElementById("storeGrid");

  function card(market) {
    const soon = market.available ? "" : " is-soon";
    const badge = market.available
      ? `<span class="store-card-meta">${market.products} ${t("stores.productCount")}</span>`
      : `<span class="store-card-meta is-soon-text">${t("common.soon")}</span>`;

    // Loqo <img>-dir, fon şəkli deyil: `alt` mətni ekran oxuyucusuna çatır və
    // fayl tapılmayanda `error` hadisəsi baş verir (fon şəklində belə hadisə
    // ümumiyyətlə yoxdur - səhv sükutla itərdi).
    // `has-logo` sinfi mətn nişanını gizlədir. Şəkil yüklənməsə, aşağıdakı
    // `wireLogoFallback()` sinfi geri götürür və ad görünür.
    const logo = market.logo
      ? `<img class="store-logo" src="${esc(market.logo)}" alt="${esc(market.name)}">`
      : "";
    const boxClass = market.logo ? "store-logo-box has-logo" : "store-logo-box";

    return (
      `<a class="store-card${soon}" href="/store/${esc(market.slug)}">` +
      `<span class="${boxClass}">${logo}` +
      `<span class="store-wordmark">${esc(market.name)}</span></span>` +
      `<span class="store-card-name">${esc(market.name)}</span>` +
      badge +
      `</a>`
    );
  }

  /**
   * Şəkil yüklənməyəndə mətn nişanına keçir.
   *
   * `onerror` atributu YAZMIRIQ: inline hadisə HTML-in içində JS deməkdir,
   * mətn isə API-dən gəlir. Hadisəni buradan bağlamaq həm təhlükəsizdir,
   * həm də bir yerdə görünür.
   */
  function wireLogoFallback() {
    for (const img of grid.querySelectorAll("img.store-logo")) {
      img.addEventListener("error", () => {
        img.closest(".store-logo-box")?.classList.remove("has-logo");
        img.remove();
      });
    }
  }

  async function load() {
    grid.innerHTML = Array.from(
      { length: 4 },
      () => `<div class="skeleton-row" style="height:150px"></div>`
    ).join("");
    try {
      const data = await (await fetch("/api/catalog/markets")).json();
      const items = data.items || [];
      if (!items.length) {
        grid.innerHTML = `<div class="notice warn">${t("stores.empty")}</div>`;
        return;
      }
      StoreColors.note(items.map((m) => m.name));
      grid.innerHTML = items.map(card).join("");
      wireLogoFallback();
    } catch (e) {
      // Şəbəkə bölməsi qırılsa da səhifənin qalanı işləməlidir.
      console.error("[stores]", e);
      grid.innerHTML =
        `<div class="notice warn">${t("stores.loadError")}` +
        `</div>`;
    }
  }

  load();

  // Dil dəyişəndə bu blok yenidən çəkilir - səhifə yenilənmir.
  // `i18n.js` hadisəni `document`-ə atır, hər modul yalnız ÖZ hissəsinə
  // baxır; beləcə heç bir modul digərinin DOM-una toxunmur.
  document.addEventListener("basketiq:lang", () => load());
})();
