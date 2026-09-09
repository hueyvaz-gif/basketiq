// ADMİN PANELİ: kataloq yükləmə, AI çıxarışı, uyğunlaşdırma, sistem statusu.
//
// AYRI FAYL OLDU (P6). Əvvəl bu kod `app.js`-in içində, istifadəçi məntiqi ilə
// yan-yana idi və HƏR ziyarətçiyə göndərilirdi. İki problem:
//
//   1. Adi istifadəçi scraping, OCR rejimi və model diaqnostikası ilə bağlı
//      kodu heç vaxt işlətmir - onlar məhsulun içidir, cavabı deyil.
//   2. Admin işarələməsi ana səhifədən çıxanda (`/admin` ayrıca ünvandır)
//      `app.js` yükləndiyi anda `#dropzone` tapa bilməzdi və İSTİFADƏÇİ
//      səhifəsi ilk sətirdən qırılardı.
//
// `esc`, `money`, `price`, `icon`, `notice` və s. `ui.js`-dədir - o, bu
// fayldan ƏVVƏL yüklənməlidir.

const $ = (sel) => document.querySelector(sel);
let selectedFile = null;

// ---------------------------------------------------------------- fayl seçimi

const dropzone = $("#dropzone");
const fileInput = $("#fileInput");

function setFile(file) {
  selectedFile = file;
  $("#fileName").textContent = file
    ? `${file.name} — ${(file.size / 1048576).toFixed(2)} MB`
    : t("admin.noFile");
  $("#uploadBtn").disabled = !file;
}

dropzone.addEventListener("click", () => fileInput.click());

// Dropzone <div>-dir, yəni klaviatura ilə "klikləmək" özü işləmir.
// role="button" verdiyimizə görə Enter/Space-i əl ilə bağlamalıyıq -
// əks halda siçansız istifadəçi fayl seçə bilmir.
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

fileInput.addEventListener("change", (e) => setFile(e.target.files[0] || null));

["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.add("over");
  })
);

["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropzone.classList.remove("over");
  })
);

dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

// ---------------------------------------------------------------- upload

$("#uploadBtn").addEventListener("click", async () => {
  if (!selectedFile) return;

  const form = new FormData();
  form.append("file", selectedFile);
  form.append("store", $("#storeInput").value.trim() || t("admin.unknownStore"));
  form.append("force_ocr", $("#forceOcr").checked ? "true" : "false");
  form.append("psm", $("#psmInput").value);

  $("#uploadBtn").disabled = true;
  notice(
    $("#uploadStatus"),
    "info",
    `<span class="spinner"></span>${t("admin.processing")}`
  );

  try {
    const res = await fetch("/api/catalogs/upload", { method: "POST", body: form });
    const data = await res.json();

    if (!res.ok) {
      notice($("#uploadStatus"), "error", esc(data.detail || t("admin.unknownError")));
      return;
    }
    if (data.duplicate) {
      notice($("#uploadStatus"), "warn", esc(data.message));
      await loadCatalogs();
      await showLines(data.catalog_id);
      return;
    }

    notice(
      $("#uploadStatus"),
      "ok",
      `${t("admin.ready", { n: `<strong>${data.stats.kept}</strong>` })}`
    );
    renderResult(data);
    await Promise.all([loadCatalogs(), loadHealth()]);
  } catch (e) {
    notice($("#uploadStatus"), "error", t("admin.networkError") + esc(e.message));
  } finally {
    $("#uploadBtn").disabled = false;
  }
});

// ---------------------------------------------------------------- nəticə

const SOURCE_LABEL = {
  pdf_text: "PDF (text layer) — OCR-siz",
  pdf_scan: "Skan PDF — OCR",
  image: t("admin.imageOcr"),
};

function renderResult(data) {
  $("#resultCard").classList.remove("hidden");
  currentCatalogId = data.catalog_id;
  $("#extractStatus").innerHTML = "";
  $("#productCard").classList.add("hidden");

  const s = data.stats;
  const dropped = Object.entries(s.dropped || {})
    .map(([k, v]) => `<span class="badge">${esc(k)} <strong>${v}</strong></span>`)
    .join("");

  $("#resultMeta").innerHTML = `
    <div class="badges">
      <span class="badge ${data.ocr_used ? "warn" : "ok"}">${esc(SOURCE_LABEL[data.source_type] || data.source_type)}</span>
      <span class="badge">${t("badge.pages")} <strong>${data.pages ?? "—"}</strong></span>
      <span class="badge">simvol <strong>${data.chars ?? "—"}</strong></span>
      <span class="badge">${t("badge.rawLines")} <strong>${s.total_lines}</strong></span>
      <span class="badge ok">${t("badge.kept")} <strong>${s.kept}</strong></span>
      <span class="badge">${t("badge.ratio")} <strong>${(s.keep_ratio * 100).toFixed(0)}%</strong></span>
    </div>
    ${dropped ? `<div class="badges">${dropped}</div>` : ""}
    ${(data.notes || []).map((n) => `<div class="notice info">${esc(n)}</div>`).join("")}
  `;

  renderLines(data.preview || []);
}

function renderLines(lines) {
  if (!lines.length) {
    $("#linesTable").innerHTML =
      `<tr><td class="txt">${t("admin.noLines")}</td></tr>`;
    return;
  }
  $("#linesTable").innerHTML = `
    <thead>
      <tr><th>#</th><th class="num">${t("common.price")}</th><th class="num">${t("col.old")}</th><th>${t("col.line")}</th></tr>
    </thead>
    <tbody>
      ${lines
        .map(
          (l, i) => `<tr>
            <td class="num">${i + 1}</td>
            <td class="num"><strong>${money(l.price)}</strong></td>
            <td class="num old">${l.old_price == null ? "" : money(l.old_price)}</td>
            <td class="txt">${esc(l.text)}</td>
          </tr>`
        )
        .join("")}
    </tbody>`;
}

// ---------------------------------------------------------------- AI çıxarış

let currentCatalogId = null;

$("#extractBtn").addEventListener("click", async () => {
  if (!currentCatalogId) return;

  const limit = $("#extractLimit").value;

  $("#extractBtn").disabled = true;
  notice(
    $("#extractStatus"),
    "info",
    `<span class="spinner"></span>${t("admin.modelWorking")}
     <br><small>${t("admin.cacheHint")}</small>`
  );

  try {
    const res = await fetch(`/api/catalogs/${currentCatalogId}/extract?limit=${limit}`, {
      method: "POST",
    });
    const data = await res.json();

    if (!res.ok) {
      notice($("#extractStatus"), "error", esc(data.detail || "Xəta"));
      return;
    }

    const llm = data.llm;
    notice(
      $("#extractStatus"),
      "ok",
      `<strong>${data.saved}</strong> ${t("admin.savedCount")} ·
       ${t("admin.fromCache")} <strong>${llm.from_cache}</strong> ·
       modeldən <strong>${llm.from_llm}</strong> ·
       uğursuz <strong>${llm.failed}</strong>`
    );
    renderProducts(data.products, data);
    await Promise.all([loadHealth(), loadCompare()]);
  } catch (e) {
    notice($("#extractStatus"), "error", t("admin.networkError") + esc(e.message));
  } finally {
    $("#extractBtn").disabled = false;
  }
});

function renderProducts(items, meta) {
  $("#productCard").classList.remove("hidden");

  $("#productMeta").innerHTML = `
    <div class="badges">
      <span class="badge"><strong>${esc(meta.store)}</strong></span>
      <span class="badge">emal olundu <strong>${meta.processed}</strong>/${meta.total_lines}</span>
      <span class="badge ok">yazıldı <strong>${meta.saved}</strong></span>
      ${meta.skipped ? `<span class="badge warn">${t("admin.skipped")} <strong>${meta.skipped}</strong></span>` : ""}
    </div>`;

  if (!items.length) {
    $("#productTable").innerHTML = `<tr><td class="txt">${t("admin.noExtract")}</td></tr>`;
    return;
  }

  $("#productTable").innerHTML = `
    <thead>
      <tr>
        <th>${t("common.product")}</th><th>${t("col.brand")}</th><th>${t("col.size")}</th>
        <th class="num">Qiymət</th><th class="num">Vahid qiymət</th><th>Kateqoriya</th>
      </tr>
    </thead>
    <tbody>
      ${items
        .map((p) => {
          const size = p.size_value != null && p.size_unit ? `${p.size_value} ${p.size_unit}` : "—";
          const unit = p.unit_price != null ? `${money(p.unit_price)} / ${p.base_unit}` : "—";
          return `<tr title="${esc(p.raw_line)}">
            <td class="txt">${esc(p.name)}</td>
            <td class="txt">${esc(p.brand || "—")}</td>
            <td class="num">${esc(size)}</td>
            <td class="num"><strong>${money(p.price)}</strong></td>
            <td class="num">${esc(unit)}</td>
            <td class="txt">${esc(t("cat." + p.category, p.category))}</td>
          </tr>`;
        })
        .join("")}
    </tbody>`;
}

async function showLines(catalogId) {
  const res = await fetch(`/api/catalogs/${catalogId}/lines?limit=200`);
  if (!res.ok) return;
  const data = await res.json();
  $("#resultCard").classList.remove("hidden");
  currentCatalogId = catalogId;
  $("#extractStatus").innerHTML = "";
  $("#productCard").classList.add("hidden");
  $("#resultMeta").innerHTML = `
    <div class="badges">
      <span class="badge"><strong>${esc(data.store)}</strong></span>
      <span class="badge">${esc(SOURCE_LABEL[data.source_type] || data.source_type)}</span>
      <span class="badge">${t("badge.rawLines")} <strong>${data.stats.total_lines}</strong></span>
      <span class="badge ok">${t("badge.kept")} <strong>${data.stats.kept}</strong></span>
    </div>`;
  renderLines(data.lines);
  $("#resultCard").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------------------------------------------------------------- kataloqlar

async function loadCatalogs() {
  try {
    const res = await fetch("/api/catalogs");
    const rows = await res.json();

    if (!rows.length) {
      $("#catalogList").innerHTML =
        `<div class="row"><span class="row-value">${t("admin.noCatalog")}</span></div>`;
      return;
    }

    $("#catalogList").innerHTML = rows
      .map(
        (r) => `<div class="row cat-row">
          <span class="entity">
            <span class="avatar is-sm" aria-hidden="true">${icon("file")}</span>
            <span class="entity-text">
              <span class="entity-name">${esc(r.store_name)}</span>
              <span class="entity-meta">#${r.id} · ${esc(SOURCE_LABEL[r.source_type] || r.source_type)} · ${esc(r.fetched_at)}</span>
            </span>
          </span>
          <span class="actions flush">
            <button class="btn btn-secondary" data-lines="${r.id}" type="button">${t("admin.lines")}</button>
            <button class="icon-btn" data-del="${r.id}" type="button"
                    aria-label="${esc(r.store_name)} kataloqunu sil">${icon("trash")}</button>
          </span>
        </div>`
      )
      .join("");

    $("#catalogList").querySelectorAll("[data-lines]").forEach((b) =>
      b.addEventListener("click", () => showLines(b.dataset.lines))
    );
    $("#catalogList").querySelectorAll("[data-del]").forEach((b) =>
      armDeleteButton(b, async () => {
        await fetch(`/api/catalogs/${b.dataset.del}`, { method: "DELETE" });
        await Promise.all([loadCatalogs(), loadHealth()]);
        $("#resultCard").classList.add("hidden");
      })
    );
  } catch {
    $("#catalogList").innerHTML = `<div class="row"><span class="row-value">${t("admin.listError")}</span></div>`;
  }
}

// SİLMƏ TƏSDİQİ (`armDeleteButton`) ARTIQ `ui.js`-DƏDİR.
//
// Səbəb: səbət səhifəsi (`basket-page.js`) də silmə düyməsi çəkir, `app.js`-i
// isə oraya qoşmaq olmur - o, yükləndiyi anda yalnız ana səhifədə mövcud olan
// elementləri axtarır. Təsdiq mexanikasının İKİ nüsxəsi olsaydı, biri
// dəyişəndə digəri köhnə qalardı və fərq yalnız real silmədə görünərdi.


// ---------------------------------------------------------------- matching

$("#matchBtn").addEventListener("click", async () => {
  $("#matchBtn").disabled = true;
  notice($("#matchStatus"), "info",
    `<span class="spinner"></span>${t("admin.matching")}`);

  try {
    const data = await (await fetch("/api/match/run?limit=20", { method: "POST" })).json();
    const pairs = (data.pairs || [])
      .map((p) => `<div class="search-item"><span>${esc(p.a)} <span class="search-meta">≡</span> ${esc(p.b)}</span>
                   <span class="search-meta">oxşarlıq ${p.similarity}</span></div>`)
      .join("");
    const rejected = (data.rejected || [])
      .map((p) => `<div class="search-item"><span class="na">${esc(p.a)} <span class="search-meta">≠</span> ${esc(p.b)}</span>
                   <span class="search-meta">oxşarlıq ${p.similarity}</span></div>`)
      .join("");

    notice($("#matchStatus"), "ok",
      `<strong>${data.llm.confirmed}</strong> cüt birləşdirildi ·
       yoxlanıldı ${data.candidates_checked}/${data.candidates_found} ·
       ${t("admin.fromCache")} ${data.llm.from_cache} · ${t("admin.fromModel")} ${data.llm.from_llm}
       ${pairs ? `<div class="gap-sm">${pairs}</div>` : ""}
       ${rejected ? `<div class="gap-sm is-muted">${rejected}</div>` : ""}`);

    await loadCompare();
  } catch (e) {
    notice($("#matchStatus"), "error", "Xəta: " + esc(e.message));
  } finally {
    $("#matchBtn").disabled = false;
  }
});

// ---------------------------------------------------------------- health

/** Statistika kartları — ikon + etiket + rəqəm + izah. */
function renderStats(db) {
  // Dördü də NEYTRAL inventar sayğacıdır: "Məhsul" qənaət deyil, "Qiymət"
  // diqqət tələb etmir. Əvvəl yaşıl/kəhrəba sırf "hamısı mavi olmasın" deyə
  // verilirdi - rəng bəzək kimi işlədilirdi. Üstəlik index.html-dəki skeleton
  // is-accent ilə başlayırdı, yəni yüklənəndə rəng sıçrayırdı.
  const cards = [
    ["store", "Market", db.stores, t("stat.storesNote"), "is-accent"],
    ["layers", "Kataloq", db.catalogs, t("stat.catalogsNote"), "is-accent"],
    ["package", "Məhsul", db.products, t("stat.productsNote"), "is-accent"],
    ["tag", "Qiymət", db.prices, t("stat.pricesNote"), "is-accent"],
  ];

  $("#stats").innerHTML = cards
    .map(
      ([ico, label, value, note, tone]) => `
      <div class="stat ${tone}">
        <div class="stat-icon">${icon(ico)}</div>
        <div class="stat-label">${label}</div>
        <div class="stat-value">${value ?? "—"}</div>
        <div class="stat-note">${note}</div>
      </div>`
    )
    .join("");
}

/**
 * Admin panelindəki status xanası: ikon + etiket + vəziyyət.
 *
 * `state` üç dəyər alır - true / false / null. Nöqtənin rəngi ondan gəlir,
 * amma rəng TƏK siqnal deyil: `sr-only` mətn vəziyyəti sözlə də deyir.
 */
function statusTile(ico, label, state, value, detail = "") {
  const cls = state === true ? "ok" : state === false ? "bad" : "warn";
  const tone = state === true ? "is-green" : state === false ? "" : "is-amber";
  const word = state === true ? t("health.ok") : state === false ? t("health.fail") : t("health.checking");
  return `<div class="status-tile">
    <span class="avatar is-sm ${tone}" aria-hidden="true">${icon(ico)}</span>
    <div class="status-tile-body">
      <span class="eyebrow">${esc(label)}</span>
      <div class="status-value">
        <span class="dot ${cls}"></span>${esc(value)}
        <span class="sr-only"> — ${word}</span>
      </div>
      ${detail ? `<div class="status-detail">${esc(detail)}</div>` : ""}
    </div>
  </div>`;
}

async function loadHealth() {
  try {
    const data = await (await fetch("/health")).json();
    if (!data.database.error) renderStats(data.database);

    const llm = data.llm;
    // Aktiv model: Claude işləyirsə o, əks halda Ollama (bax: ai/llm.py).
    const activeModel = llm.claude_active ? llm.claude_model : llm.model;

    $("#status").innerHTML = [
      statusTile("database", t("health.database"), !data.database.error,
        data.database.error ? t("admin.error") : t("health.connected"),
        data.database.error || ""),
      statusTile("sparkle", t("health.llmProvider"), llm.claude_active || llm.reachable,
        llm.status || llm.provider,
        llm.claude_note || ""),
      statusTile("cpu", t("health.activeModel"), llm.claude_active || llm.model_available,
        activeModel,
        llm.claude_active ? t("health.fallback") + llm.model : ""),
      statusTile("server", t("health.ollama"), llm.reachable,
        llm.reachable ? t("health.reachable") : t("health.unreachable"),
        llm.reachable ? llm.base_url : (llm.error || "")),
      statusTile("terminal", t("health.environment"), true, data.env),
    ].join("");
  } catch {
    $("#status").innerHTML = statusTile("server", "Backend", false, t("health.noResponse"),
      t("health.uvicorn"));
  }
}

loadHealth();
loadCatalogs();

// Dil dəyişəndə dinamik bloklar yenidən çəkilir.
document.addEventListener("basketiq:lang", () => {
  loadHealth();
  loadCatalogs();
});
