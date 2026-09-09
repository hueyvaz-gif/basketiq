// Profil və profilə uyğun tövsiyə.
//
// Profil sadəcə ayar deyil - tövsiyə məntiqini dəyişir. Ona görə formanın
// altında dərhal "bu ayarlarla nə tövsiyə olunur?" göstərilir: istifadəçi
// dəyişikliyin nəticəsini elə orada görür.

(() => {
  const sel = (id) => document.getElementById(id);

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  const money = (v) => (v == null ? "—" : Number(v).toFixed(2));

  function read() {
    return {
      household_size: Number(sel("profHousehold").value) || 1,
      weekly_budget: sel("profBudget").value ? Number(sel("profBudget").value) : null,
      max_stores: Number(sel("profStores").value) || 1,
      min_split_saving: Number(sel("profMinSaving").value) || 0,
      prefer_unit_price: sel("profUnitPrice").checked,
      avoid: sel("profAvoid").value.split(",").map((s) => s.trim()).filter(Boolean),
    };
  }

  function fill(data) {
    sel("profHousehold").value = data.household_size;
    sel("profBudget").value = data.weekly_budget ?? "";
    sel("profStores").value = data.max_stores;
    sel("profMinSaving").value = data.min_split_saving;
    sel("profUnitPrice").checked = data.prefer_unit_price;
    sel("profAvoid").value = (data.avoid || []).join(", ");
    sel("profSummary").innerHTML = `<div class="notice">${esc(data.summary || "")}</div>`;
  }

  async function load() {
    try {
      fill(await (await fetch("/api/profile")).json());
      await loadPlan();
    } catch {
      sel("profSummary").innerHTML = `<div class="notice error">${t("profile.loadError")}</div>`;
    }
  }

  async function save() {
    const btn = sel("profSaveBtn");
    btn.disabled = true;
    btn.textContent = t("profile.saving");
    try {
      const res = await fetch("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(read()),
      });
      if (!res.ok) throw new Error(t("profile.serverError"));
      fill(await res.json());
      await loadPlan();
    } catch (e) {
      sel("profSummary").innerHTML = `<div class="notice error">${t("admin.errorPrefix")}${esc(e.message)}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Yadda saxla";
    }
  }

  async function loadPlan() {
    const box = sel("planBox");
    let data;
    try {
      data = await (await fetch("/api/profile/recommend")).json();
    } catch {
      box.innerHTML = `<div class="notice error">${t("profile.planError")}</div>`;
      return;
    }

    const parts = [];

    if (data.plan === "yoxdur") {
      parts.push(`<div class="notice">${esc(data.notes[0] || t("profile.noPlan"))}</div>`);
      box.innerHTML = parts.join("");
      return;
    }

    const planLabel = data.plan === "bolunmus" ? t("profile.split") : t("profile.single");
    parts.push(`<div class="row">
        <span class="row-label"><strong>${esc(planLabel)}</strong> — ${esc(data.stores.join(", "))}</span>
        <span class="row-value"><strong>${money(data.total)} AZN</strong></span>
      </div>`);

    // İki variantı yan-yana göstəririk: istifadəçi "nə itirirəm?" sualının
    // cavabını görməlidir, yalnız seçilmiş planı yox.
    if (data.single_total != null && data.split_total != null) {
      parts.push(`<div class="row">
          <span class="row-label">${t("profile.singleVsSplit")}</span>
          <span class="row-value">${money(data.single_total)} / ${money(data.split_total)} AZN
            ${data.split_saving ? `${t("profile.diff", { amount: money(data.split_saving) })}` : ""}</span>
        </div>`);
    }

    for (const note of data.notes) {
      parts.push(`<div class="row"><span class="row-value" style="opacity:.8">${esc(note)}</span></div>`);
    }
    for (const warn of data.warnings) {
      parts.push(`<div class="notice warn">${esc(warn)}</div>`);
    }

    if (data.plan === "bolunmus" && data.assignments.length) {
      parts.push(`<div class="table-scroll gap-md"><table class="lines">
        <thead><tr>
          <th scope="col">Məhsul</th><th scope="col">Market</th>
          <th scope="col" class="num">Qiymət</th>
        </tr></thead><tbody>` +
        data.assignments
          .map(
            (a) => `<tr>
              <td class="txt">${esc(a.label)}</td>
              <td class="txt">${a.store ? esc(a.store) : `<em>${t("profile.notFound")}</em>`}</td>
              <td class="num">${money(a.price)}</td>
            </tr>`
          )
          .join("") +
        `</tbody></table></div>`);
    }

    if (data.budget) {
      const b = data.budget;
      parts.push(`<div class="row">
          <span class="row-label">Büdcə</span>
          <span class="row-value">${money(b.total)} / ${money(b.limit)} AZN —
            ${b.fits ? t("profile.fits") : `<strong>${t("profile.over", { amount: money(b.over) })}</strong>`}</span>
        </div>`);
    }

    for (const tip of data.bulk_tips || []) {
      parts.push(`<div class="notice">
        <strong>${esc(tip.better)}</strong> (${esc(tip.better_size)}) —
        vahid qiymət ${money(tip.better_unit_price)} AZN,
        indikindən ${tip.gain_pct}% aşağı (${esc(tip.store)}).
      </div>`);
    }

    box.innerHTML = parts.join("");
  }

  sel("profSaveBtn").addEventListener("click", save);
  sel("planRefresh").addEventListener("click", loadPlan);
  load();

  // Dil dəyişəndə bu modul öz blokunu yenidən çəkir - səhifə yenilənmir.
  document.addEventListener("basketiq:lang", () => {
    load();
  });
})();
