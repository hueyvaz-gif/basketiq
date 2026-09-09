// Karantin növbəsi — nişanlanmış qiymət sətirlərinin admin baxışı (C12).
//
// NİYƏ AYRICA FAYL? `app.js` kataloq yükləmə axınıdır və yükləndiyi anda
// `#dropzone` kimi elementləri axtarır. Növbə isə yalnız admin panelində var
// və məhsul/axtarış səhifələrində ÜMUMİYYƏTLƏ olmur — ayrı fayl olanda biri
// digərini qırmır.
//
// SƏTİR SİYAHIDAN DƏRHAL SİLİNMİR. Təsdiqdən sonra sətir yerində qalır və
// «Təsdiqləndi» yazısı ilə sönükləşir: adminin ardıcıl on sətrə baxdığı halda
// siyahı ayağının altından sürüşməsin. Yenilə düyməsi (dil dəyişməsi və ya
// səhifə yenilənməsi) təmiz siyahı gətirir.

(() => {
  const list = document.getElementById("reviewList");
  if (!list) return; // admin paneli olmayan səhifədə fayl sakitcə dayanır

  const flagPill = (name) => {
    // `deepDiscount` qırmızı, kənarlaşmalar sarı: dərin endirim istifadəçini
    // birbaşa yanıldır, kənarlaşma isə çox vaxt sadəcə nadir məhsuldur.
    const kind = name === "deepDiscount" ? "is-red" : "is-amber";
    return `<span class="pill ${kind}">${esc(t("flag." + name, name))}</span>`;
  };

  function row(item) {
    const köhnə =
      item.old_price != null
        ? ` <span class="row-note">${esc(t("review.was"))} ${money(item.old_price)} ₼</span>`
        : "";
    const faiz = item.discount_pct != null ? ` −${item.discount_pct}%` : "";

    return `<div class="row is-review" data-price="${item.price_id}">
        <span class="row-label">
          <strong>${esc(item.product)}</strong> · ${esc(item.store)}${faiz}${köhnə}
          <span class="row-raw">${esc(item.raw_line || "")}</span>
        </span>
        <span class="row-value">
          ${price(item.price)}
          ${item.flags.map(flagPill).join(" ")}
          <button class="btn btn-ghost" type="button" data-approve="${item.price_id}">
            ${esc(t("review.approve"))}
          </button>
        </span>
      </div>`;
  }

  async function load() {
    try {
      const res = await fetch("/api/review/flagged?limit=50");
      const data = await res.json();
      if (!res.ok) throw new Error("http");

      if (!data.items.length) {
        list.innerHTML = `<div class="notice ok">${esc(t("review.empty"))}</div>`;
        return;
      }
      // Ümumi say siyahının uzunluğundan FƏRQLİ ola bilər (limit 50) —
      // admin nə qədər işin qaldığını görməlidir.
      list.innerHTML =
        `<div class="badges"><span class="badge warn">${esc(
          t("review.total", { n: data.total })
        )}</span></div>` + data.items.map(row).join("");
    } catch {
      list.innerHTML = `<div class="notice error">${esc(t("review.loadError"))}</div>`;
    }
  }

  async function approve(priceId, btn) {
    btn.disabled = true;
    try {
      const res = await fetch(`/api/review/flagged/${priceId}/approve`, { method: "POST" });
      if (!res.ok) throw new Error("http");
      const sətir = btn.closest(".row");
      sətir.classList.add("is-done");
      // Düymə mətnə çevrilir: təkrar basmaq mümkün olmasın, amma nəticə görünsün.
      btn.outerHTML = `<span class="pill is-green">${esc(t("review.approved"))}</span>`;
    } catch {
      btn.disabled = false;
      list.insertAdjacentHTML(
        "afterbegin",
        `<div class="notice error">${esc(t("review.loadError"))}</div>`
      );
    }
  }

  // Hadisə DELEQASİYASI: siyahı hər yükləmədə yenidən qurulur, ona görə
  // düymələrə tək-tək dinləyici bağlamaq mənasızdır.
  list.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-approve]");
    if (btn) approve(Number(btn.dataset.approve), btn);
  });

  load();
  document.addEventListener("basketiq:lang", load);
})();
