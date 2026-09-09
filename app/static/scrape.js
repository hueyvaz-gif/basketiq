// Mənbədən avtomatik kataloq çəkmə.
//
// Niyə ayrıca fayl? app.js manual upload axınıdır; scraping ondan asılı deyil
// və ayrı saxlansa, biri dəyişəndə digəri qırılmır.
//
// Sorğu UZUN çəkir (OCR dəqiqələrlə). Ona görə düymə bloklanır və istifadəçiyə
// nə qədər gözləyəcəyi əvvəlcədən deyilir - "donub qalıb?" sualı yaranmasın.

(() => {
  const sel = (id) => document.getElementById(id);

  const html = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  async function loadSources() {
    const box = sel("sourceList");
    try {
      const sources = await (await fetch("/api/scrape/sources")).json();

      // DÖRD MARKETİN HAMISI GÖRÜNÜR (D14). Çəkilə bilməyən mənbə siyahıdan
      // ÇIXARILMIR - onda «niyə yalnız bir market var?» sualı cavabsız qalardı.
      // Əvəzində düyməsi sönür və yanında ölçülmüş səbəb yazılır.
      box.innerHTML = sources
        .map((s) => {
          const bağlı = !s.scrapeable;
          return `<label class="check${bağlı ? " is-off" : ""}">
                    <input type="radio" name="scrapeSource" value="${html(s.key)}"
                           ${bağlı ? "disabled" : ""}>
                    <span>
                      <strong>${html(s.store)}</strong>
                      <span class="pill">${html(s.format)}</span>
                      <span class="pill ${bağlı ? "is-amber" : "is-green"}">${html(
                        t("source." + s.status, s.status)
                      )}</span>
                      <span class="check-note">${html(s.note || s.page_url || "")}</span>
                    </span>
                  </label>`;
        })
        .join("");

      // Defolt seçim yalnız İŞLƏK mənbədən olur - əks halda düyməyə basan
      // istifadəçi bağlı mənbə ilə qarşılaşardı.
      const first = box.querySelector("input:not([disabled])");
      if (first) first.checked = true;
    } catch {
      box.innerHTML = `<div class="notice error">${t("scrape.listError")}</div>`;
    }
  }

  async function runScrape() {
    const chosen = document.querySelector('input[name="scrapeSource"]:checked');
    const status = sel("scrapeStatus");
    const btn = sel("scrapeBtn");
    if (!chosen) {
      status.innerHTML = `<div class="notice warn">${t("scrape.pickFirst")}</div>`;
      return;
    }

    const pages = Number(sel("scrapePages").value);
    btn.disabled = true;
    // innerHTML, textContent DEYİL: düymənin içində SVG ikon var və
    // textContent onu silərdi - sonra geri qaytarmaq üçün də ikon lazımdır.
    btn.innerHTML = `<span class="spinner"></span>${t("scrape.working")}`;
    status.innerHTML = `<div class="notice">
        Səhifə açılır, PDF endirilir, sonra OCR işləyir.
        ${pages} səhifə üçün təxminən ${pages * 20} saniyə çəkə bilər — gözlə.
      </div>`;

    try {
      const url = `/api/scrape/${encodeURIComponent(chosen.value)}?max_files=1&max_pages=${pages}`;
      const res = await fetch(url, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || t("profile.serverError"));
      render(status, data);
      if (typeof loadCatalogs === "function") loadCatalogs();
    } catch (e) {
      status.innerHTML = `<div class="notice error">${t("admin.errorPrefix")}${html(e.message)}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML =
        `<svg aria-hidden="true"><use href="#icon-download"></use></svg> ${t("admin.scrapeBtn")}`;
    }
  }

  function render(el, data) {
    const parts = [];

    parts.push(`<div class="notice ok">
        ${data.found_count} kataloq linki tapıldı,
        ${data.ingested.length} emal olundu,
        ${data.skipped.length} ötürüldü.
      </div>`);

    for (const item of data.ingested) {
      const stats = item.stats || {};
      parts.push(`<div class="row">
          <span class="row-label">#${item.catalog_id} ${html(item.filename)}</span>
          <span class="row-value">
            ${item.size_mb} MB · ${html(item.source_type)} ·
            ${stats.kept ?? 0}/${stats.total_lines ?? 0} sətir
          </span>
        </div>`);
      for (const note of item.notes || []) {
        parts.push(`<div class="row"><span class="row-value">${html(note)}</span></div>`);
      }
      // İlk sətirlər - OCR-in nə oxuduğunu dərhal görmək üçün
      for (const line of (item.preview || []).slice(0, 5)) {
        parts.push(`<div class="row">
            <span class="row-label">${html(line.text).slice(0, 70)}</span>
            <span class="row-value">${line.price ?? "—"}</span>
          </div>`);
      }
    }

    for (const item of data.skipped) {
      parts.push(`<div class="row">
          <span class="row-label">#${item.catalog_id}</span>
          <span class="row-value">ötürüldü — ${html(item.reason)}</span>
        </div>`);
    }

    for (const err of data.errors) {
      parts.push(`<div class="notice error">${html(err)}</div>`);
    }

    el.innerHTML = parts.join("");
  }

  sel("scrapeBtn").addEventListener("click", runScrape);
  loadSources();

  // Dil dəyişəndə bu modul öz blokunu yenidən çəkir - səhifə yenilənmir.
  document.addEventListener("basketiq:lang", () => {
    loadSources();
  });
})();
