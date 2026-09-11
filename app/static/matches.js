/* ============================================================================
   UYĞUNLAŞDIRMA YOXLAMASI (ADDIM 5) — `/admin/matches`.

   Data: `GET /api/match/review?status=pending|llm` (app/match_review.py).
   Qərar: `POST /api/match/decide` — insan qərarı hər şeyin üstündədir,
   qruplar serverdə DƏRHAL yenidən qurulur (ai/matcher.py:decide).

   `applied=false` NƏ DEMƏKDİR? İnsan «bəli» dedi, amma birləşmə qadağaya
   düşdü: bir qrupda eyni marketin iki məhsulu və ya iki fərqli ölçü olardı.
   Qərar yenə yazılır. Ekran bunu GİZLƏTMİR — əks halda adam «birləşdirdim»
   düşünər, səbət isə dəyişməz.

   İKİ DÜYMƏ EYNİ ÇƏKİDƏDİR (ikisi də ikinci dərəcəli). Doldurulmuş mavi
   «Bəli» göz üçün «tövsiyə olunan cavab» deməkdir və insanı birləşdirməyə
   itələyərdi — halbuki səhv birləşdirmə səhv ayırmaqdan PİSDİR (MATCH_PROMPT
   da elə deyir). Üstəlik ekranda 30 doldurulmuş düymə olardı.

   LLM QƏRARI `is-ai` nişanıdır, yaşıl/qırmızı yox: bu, heç kimin
   təsdiqləmədiyi maşın təxminidir — «təsdiqlənib» və ya «xəta» rəngi onu
   olduğundan etibarlı və ya təhlükəli göstərərdi.

   KATALOQ SƏTRİ NİYƏ GÖSTƏRİLİR? Ölçüsüz kataloq məhsulu haqqında qərar
   verən adam ölçünü çox vaxt OCR mətnində görür — maşın onu oxuya bilmədi.
   ============================================================================ */

const $ = (sel) => document.querySelector(sel);

const state = { queue: "pending", pairs: [], busy: false };

// Kart sürüşüb çıxandan sonra silinir. Müddət CSS-dən OXUNUR (`--ease`):
// əl ilə yazılmış rəqəm token dəyişəndə ondan ayrılardı. `prefers-reduced-
// motion` keçidi söndürəndə müddət 0 olur və kart dərhal gedir -
// `transitionend` gözlənilsəydi, o hadisə heç gəlməzdi və kart ekranda qalardı.
const leaveMs = (el) => (parseFloat(getComputedStyle(el).transitionDuration) || 0) * 1000;

function offerHtml(o) {
  const layer = o.layer === "site" ? "matches.shelf" : "matches.catalog";
  return `
    <li class="match-offer">
      ${storeChip(o.store)}
      <span class="match-price num">${price(o.price)}</span>
      <span class="pill">${esc(t(layer))}</span>
      ${o.raw_line ? `<span class="row-raw">${esc(o.raw_line)}</span>` : ""}
    </li>`;
}

function sideHtml(p) {
  if (!p) return `<div class="match-side">${esc(t("matches.error"))}</div>`;
  const size = p.size
    ? `<span class="badge">${esc(p.size)}</span>`
    : `<span class="pill is-amber">${esc(t("matches.reasonSize"))}</span>`;
  const offers = p.offers.length
    ? p.offers.map(offerHtml).join("")
    : `<li class="match-offer">${esc(t("matches.noPrice"))}</li>`;
  return `
    <div class="match-side">
      <div class="match-thumb">${productThumb(p)}</div>
      <div class="match-info">
        <div class="match-name">${esc(p.label)}</div>
        ${size}
        <ul class="match-offers">${offers}</ul>
      </div>
    </div>`;
}

function verdictPill(pair) {
  if (pair.decision === "pending") {
    return `<span class="pill is-amber">${icon("alert")}${esc(t("matches.reasonSize"))}</span>`;
  }
  const key = pair.decision === "same" ? "matches.llmSame" : "matches.llmDifferent";
  return `<span class="pill is-ai">${icon("sparkle")}${esc(t(key))}</span>`;
}

function pairHtml(pair, index) {
  const score = Math.round((pair.similarity ?? 0) * 100);
  // Kartın adı: ekran oxuyucusu 30 eyni «Bəli / Xeyr» düyməsindən hansının
  // hansı cütə aid olduğunu bilsin.
  const name = `${pair.a?.label ?? ""} — ${pair.b?.label ?? ""}`;
  return `
    <article class="card match-pair" data-index="${index}" aria-label="${esc(name)}">
      <div class="match-meta">
        ${verdictPill(pair)}
        <span class="eyebrow">${esc(t("matches.similarity"))} ${score}%</span>
      </div>
      <div class="match-sides">
        ${sideHtml(pair.a)}
        <div class="match-vs" aria-hidden="true">?</div>
        ${sideHtml(pair.b)}
      </div>
      <div class="actions flush">
        <button class="btn btn-secondary" type="button" data-same="1">
          ${icon("check")}<span>${esc(t("matches.same"))}</span>
        </button>
        <button class="btn btn-secondary" type="button" data-same="0">
          <span>${esc(t("matches.different"))}</span>
        </button>
      </div>
    </article>`;
}

function renderCounts(counts) {
  $("#countPending").textContent = counts ? counts.pending : "—";
  $("#countLlm").textContent = counts ? counts.llm : "—";
}

function render() {
  const open = state.pairs.filter((p) => !p.done);
  $("#matchList").innerHTML = open.length
    ? state.pairs.map((p, i) => (p.done ? "" : pairHtml(p, i))).join("")
    : `<div class="notice ok">${esc(t("matches.empty"))}</div>`;
}

async function load() {
  try {
    const res = await fetch(`/api/match/review?status=${state.queue}&limit=30`);
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    state.pairs = data.pairs;
    renderCounts(data.counts);
    render();
  } catch {
    // Skelet QALMAMALIDIR: ekran eyni anda «xəta» və «yüklənir» deməsin.
    state.pairs = [];
    renderCounts(null);
    $("#matchList").innerHTML = "";
    notice($("#matchStatus"), "error", esc(t("matches.error")));
  }
}

async function decide(card, same) {
  if (state.busy) return;
  const pair = state.pairs[Number(card.dataset.index)];
  const buttons = card.querySelectorAll("button");
  state.busy = true;
  buttons.forEach((b) => { b.disabled = true; });

  try {
    const res = await fetch("/api/match/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ a_id: pair.a_id, b_id: pair.b_id, same }),
    });
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();

    renderCounts(data.counts);
    pair.done = true;
    if (data.applied) {
      $("#matchStatus").innerHTML = "";
      // Uğur da eşidilməlidir - yalnız xəta və qadağa deyil.
      $("#matchLive").textContent = t("matches.saved");
    } else {
      notice($("#matchStatus"), "warn", esc(t("matches.refused")));
    }

    // FOKUS İTMƏMƏLİDİR: fokuslu düymə kartla birlikdə silinir və fokus
    // `<body>`-yə düşərdi - klaviatura ilə işləyən adam hər cütdən sonra
    // yuxarıdan başlamalı olardı. Növbəti kartın birinci düyməsinə keçir.
    const next = card.nextElementSibling;
    card.classList.add("is-leaving");
    setTimeout(async () => {
      if (state.pairs.every((p) => p.done)) {
        await load();
        $("#matchList").focus();
        return;
      }
      card.remove();
      const target = next && next.querySelector("button");
      (target || $("#matchList")).focus();
    }, leaveMs(card));
  } catch {
    buttons.forEach((b) => { b.disabled = false; });
    notice($("#matchStatus"), "error", esc(t("matches.error")));
  } finally {
    state.busy = false;
  }
}

// --- Tablar: klik + ox düymələri (WAI-ARIA tab nümunəsi) -----------------
const tabs = [...document.querySelectorAll(".seg-btn[data-queue]")];

function selectTab(tab, focus) {
  state.queue = tab.dataset.queue;
  tabs.forEach((other) => {
    const on = other === tab;
    other.setAttribute("aria-selected", String(on));
    other.tabIndex = on ? 0 : -1;
  });
  $("#matchList").setAttribute("aria-labelledby", tab.id);
  if (focus) tab.focus();
  $("#matchStatus").innerHTML = "";
  load();
}

tabs.forEach((tab, i) => {
  tab.addEventListener("click", () => selectTab(tab, false));
  tab.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const step = e.key === "ArrowRight" ? 1 : tabs.length - 1;
    selectTab(tabs[(i + step) % tabs.length], true);
  });
});

$("#matchList").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-same]");
  if (!btn) return;
  decide(btn.closest(".match-pair"), btn.dataset.same === "1");
});

// Dil dəyişəndə kartlar yenidən çəkilir (mətnlər JS-dədir). Hadisə
// `document`-ə atılır (i18n.js) və qabarmır - `window` onu eşitməzdi.
document.addEventListener("basketiq:lang", render);

(window.IconsReady || Promise.resolve()).then(load);
