// REKLAM MENECERİ (E22) — sifarişlərin yaradılması, dayandırılması, silinməsi
// və hesabat rəqəmləri.
//
// NİYƏ AYRICA FAYL? `ads.js` istifadəçi tərəfidir və HƏR ziyarətçidə işləyir;
// bu fayl isə yalnız admin panelində mövcud olan elementləri axtarır. Bir
// faylda olsaydılar, admin bağlı olanda (B11) istifadəçi tərəfi də qırılardı.
//
// SİLMƏ TƏSDİQİN ARXASINDADIR: `armDeleteButton()` (app.js) ikinci kliki
// gözləyir. Bu, layihənin ümumi qaydasıdır - kataloq və səbət silmələri də
// eyni funksiyadan keçir, yəni davranış hər yerdə eynidir.

(() => {
  const list = document.getElementById("adsList");
  const form = document.getElementById("adForm");
  if (!list || !form) return;

  const sel = (id) => document.getElementById(id);

  let slots = [];

  const tarixAralığı = (ad) => `${ad.starts_at} — ${ad.ends_at}`;

  /** Sifariş bu gün ekranda görünürmü? Admin «niyə görünmür?» sualını burada həll edir. */
  function canlı(ad) {
    const bugün = new Date().toISOString().slice(0, 10);
    return ad.active && ad.on_page !== false && ad.starts_at <= bugün && ad.ends_at >= bugün;
  }

  function sətir(ad) {
    // SƏHİFƏDƏ OLMAYAN YER (2026-09-11): sifariş aktiv və vaxtında olsa da
    // görünmür. Əvvəl belə sifariş «efirdə» yazılırdı - admin reklamı canlı
    // sanırdı, halbuki göstərim sayı 0 idi. Səbəb elə bu nişandadır.
    const hal = ad.on_page === false
      ? `<span class="pill is-red">${esc(t("adsAdmin.offPage"))}</span>`
      : canlı(ad)
        ? `<span class="pill is-green">${esc(t("adsAdmin.live"))}</span>`
        : `<span class="pill is-amber">${esc(t("adsAdmin.paused"))}</span>`;

    const nümunə = ad.is_sample
      ? `<span class="pill">${esc(t("adsAdmin.sample"))}</span>`
      : "";

    return `<tr>
        <td class="txt">
          <strong>${esc(ad.title)}</strong> ${hal} ${nümunə}
          <span class="row-raw">${esc(ad.advertiser)} · ${esc(ad.target_url)}</span>
        </td>
        <td class="txt">${esc(ad.slot)}<span class="row-note">${esc(tarixAralığı(ad))}</span></td>
        <td class="num">${ad.impressions}</td>
        <td class="num">${ad.clicks}</td>
        <td class="num">
          <button class="btn btn-ghost" type="button" data-toggle="${ad.id}"
                  data-active="${ad.active ? "1" : "0"}">
            ${esc(ad.active ? t("adsAdmin.pause") : t("adsAdmin.resume"))}
          </button>
          <button class="icon-btn" type="button" data-del-ad="${ad.id}"
                  aria-label="${esc(ad.title)}">${icon("trash")}</button>
        </td>
      </tr>`;
  }

  async function load() {
    try {
      const res = await fetch("/api/admin/ads");
      if (!res.ok) throw new Error("http");
      const data = await res.json();
      slots = data.slots || [];

      // Slot seçimi REYESTRDƏN gəlir, HTML-də sabit yazılmır: kodda yeni yer
      // açılanda forma özü yenilənir, əks halda admin mövcud olmayan slota
      // sifariş yazardı və reklam heç yerdə görünməzdi.
      sel("adSlotSelect").innerHTML = slots
        .map((s) => `<option value="${esc(s.key)}">${esc(s.label)}</option>`)
        .join("");

      list.innerHTML = data.items.length
        ? `<table class="lines is-dense">
             <thead><tr>
               <th scope="col">${esc(t("adsAdmin.ad"))}</th>
               <th scope="col">${esc(t("adsAdmin.slot"))}</th>
               <th scope="col" class="num">${esc(t("adsAdmin.impressions"))}</th>
               <th scope="col" class="num">${esc(t("adsAdmin.clicks"))}</th>
               <th scope="col" class="num"><span class="sr-only">${esc(t("col.action"))}</span></th>
             </tr></thead>
             <tbody>${data.items.map(sətir).join("")}</tbody>
           </table>`
        : `<div class="notice">${esc(t("adsAdmin.empty"))}</div>`;

      wire();
    } catch {
      list.innerHTML = `<div class="notice error">${esc(t("adsAdmin.loadError"))}</div>`;
    }
  }

  function wire() {
    for (const btn of list.querySelectorAll("[data-toggle]")) {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        await fetch(`/api/admin/ads/${btn.dataset.toggle}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ active: btn.dataset.active !== "1" }),
        });
        load();
      });
    }

    for (const btn of list.querySelectorAll("[data-del-ad]")) {
      armDeleteButton(btn, async () => {
        await fetch(`/api/admin/ads/${btn.dataset.delAd}`, { method: "DELETE" });
        load();
      });
    }
  }

  /** Kreativ faylı əvvəlcə yüklənir, sonra ünvanı sifarişə yazılır. */
  async function uploadCreative() {
    const input = sel("adCreative");
    if (!input.files || !input.files[0]) return null;

    const body = new FormData();
    body.append("file", input.files[0]);
    const res = await fetch("/api/admin/ads/creative", { method: "POST", body });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || t("adsAdmin.saveError"));
    return data.path;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = sel("adFormStatus");
    const btn = sel("adSubmit");
    btn.disabled = true;
    status.innerHTML = "";

    try {
      const image_path = await uploadCreative();
      const res = await fetch("/api/admin/ads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          advertiser: sel("adAdvertiser").value.trim(),
          title: sel("adTitle").value.trim(),
          body: sel("adBody").value.trim(),
          target_url: sel("adUrl").value.trim(),
          slot: sel("adSlotSelect").value,
          starts_at: sel("adStart").value,
          ends_at: sel("adEnd").value,
          image_path,
          active: sel("adActive").checked,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || t("adsAdmin.saveError"));

      form.reset();
      sel("adActive").checked = true;
      status.innerHTML = `<div class="notice ok">${esc(t("adsAdmin.saved"))}</div>`;
      load();
    } catch (err) {
      status.innerHTML = `<div class="notice error">${esc(String(err.message))}</div>`;
    } finally {
      btn.disabled = false;
    }
  });

  load();
  document.addEventListener("basketiq:lang", load);
})();
