// MARKET ƏHATƏSİ (D15) — admin panelindəki cədvəl.
//
// Bir sual, bir cədvəl: hansı marketin datası var, nə qədər, nə vaxt gəlib.
// Əvvəl bu cavab üç yerə səpələnmişdi (baza sayğacları, kataloq siyahısı,
// ana səhifədəki «Tezliklə» yazısı) və heç biri «Bravo nə vaxt yeniləndi?»
// sualına cavab vermirdi.
//
// «AKTİVLƏŞDİR» DÜYMƏSİ YOXDUR VƏ QƏSDƏN YOXDUR: market datası düşən kimi
// ana səhifədə özü işlək olur. Əl ilə aktivləşdirmə iki həqiqət yaradardı -
// «aktiv, amma boş» market istifadəçiyə boş cədvəl kimi görünərdi.

(() => {
  const box = document.getElementById("coverageTable");
  if (!box) return;

  const tarix = (s) => (s ? String(s).slice(0, 16) : `<span class="row-note">${t("coverage.never")}</span>`);

  function sətir(m) {
    const durum = m.available
      ? `<span class="pill is-green">${esc(t("coverage.live"))}</span>`
      : `<span class="pill is-amber">${esc(t("common.soon"))}</span>`;

    return `<tr>
        <td class="txt"><strong>${esc(m.name)}</strong> ${durum}</td>
        <td class="num">${m.products}</td>
        <td class="num">${m.prices}</td>
        <td class="num">${m.coverage_pct}%</td>
        <td class="num">${tarix(m.last_seen)}</td>
        <td class="txt">
          <span class="pill">${esc(m.source_format || "—")}</span>
          <span class="pill">${esc(t("source." + m.source_status, m.source_status || "—"))}</span>
          <span class="row-note">${esc(m.source_note || "")}</span>
        </td>
      </tr>`;
  }

  async function load() {
    try {
      const res = await fetch("/api/admin/coverage");
      if (!res.ok) throw new Error("http");
      const data = await res.json();

      box.innerHTML = `<table class="lines is-dense">
          <thead><tr>
            <th scope="col">${esc(t("coverage.market"))}</th>
            <th scope="col" class="num">${esc(t("common.products"))}</th>
            <th scope="col" class="num">${esc(t("common.price"))}</th>
            <th scope="col" class="num">${esc(t("coverage.share"))}</th>
            <th scope="col" class="num">${esc(t("coverage.updated"))}</th>
            <th scope="col">${esc(t("coverage.source"))}</th>
          </tr></thead>
          <tbody>${data.items.map(sətir).join("")}</tbody>
        </table>`;
    } catch {
      box.innerHTML = `<div class="notice error">${esc(t("coverage.loadError"))}</div>`;
    }
  }

  load();
  document.addEventListener("basketiq:lang", load);
})();
