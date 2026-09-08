// Qiymət tarixçəsi qrafiki və endirim yoxlaması.
//
// Chart.js CDN-dən yüklənir. Yüklənməsə səhifə qırılmır - qrafikin yerinə
// izah göstərilir, cədvəllər isə işləməyə davam edir. Səbəb: dashboard
// internetsiz də açıla bilməlidir; qrafik faydalıdır, amma kritik deyil.

(() => {
  const sel = (id) => document.getElementById(id);

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  // ------------------------------------------------------------------ rənglər
  //
  // Qrafik rəngləri CSS-dən OXUNUR, burada yazılmır.
  //
  // Niyə? Chart.js canvas-a çəkir - canvas isə CSS dəyişənlərini bilmir, ona
  // hazır rəng sətri lazımdır. Əgər rəngi bura hardcode etsək, `--accent`
  // dəyişəndə səhifə bir rəngdə, qrafik başqa rəngdə qalardı. Token-i JS ilə
  // oxumaq bu ayrılığın qarşısını alır: mənbə yenə də style.css-dir.

  const cssVar = (name, fallback) => {
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return value || fallback;
  };

  // color-mix() dəyərləri getComputedStyle-dan həmişə hesablanmış gəlmir,
  // ona görə YALNIZ sadə token-lər oxunur, çalarlar isə burada qurulur.
  //
  // TOKEN ADLARI v2-də DƏYİŞDİ. Əvvəl burada `--green` və `--amber` oxunurdu;
  // trolley palitrasına keçəndə onlar `--ok` və `--info` oldu. Bu sətirlər
  // yenilənməsəydi, `cssVar()` boş qaytarıb SƏSSİZCƏ köhnə hardcode rəngə
  // düşərdi - qrafik yenə çəkilər, sadəcə səhifə ilə fərqli rəngdə olardı.
  // Ehtiyat dəyərlər də palitranın özündən götürülüb.
  const TOKENS = {
    accent: cssVar("--accent", "#00a300"),
    green: cssVar("--ok", "#4caf50"),
    amber: cssVar("--info", "#0066b7"),
    text2: cssVar("--text-2", "#525252"),
    text: cssVar("--text", "#000000"),
    surface: cssVar("--surface", "#f1f3f4"),
  };

  /** #RRGGBB -> rgba(...) — şəffaflıq üçün. */
  function alpha(hex, a) {
    const m = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(hex.trim());
    if (!m) return hex;
    const [r, g, b] = m.slice(1).map((h) => parseInt(h, 16));
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }

  // Trend qrafikində hər marketə SABİT rəng lazımdır: leqenda var və eyni
  // market iki qrafikdə eyni rəngdə görünməlidir.
  //
  // Palitra layihənin öz token-lərindən qurulur - bənövşəyi/çəhrayı yoxdur.
  // Market palitrası CSS-dəki `--store-1..6` ilə EYNİDİR: eyni market
  // qrafikdə və cədvəldə eyni rəngdə görünsün. Yaşıl/qırmızı YOXDUR -
  // onlar status rəngidir, market kimliyi ilə qarışmamalıdır.
  const STORE_COLORS = [1, 2, 3, 4, 5, 6].map((i) => cssVar(`--store-${i}`, TOKENS.accent));

  // Xananı `store-colors.js` hesablayır - BURADA İKİNCİ REYESTR SAXLAMIRIQ.
  //
  // Əvvəl bu fayl öz Map-ini ƏLİFBA sırası ilə, app.js isə API sırası ilə
  // doldururdu. API sırası qiymətə görədir, əlifbaya görə deyil, ona görə eyni
  // market cədvəldə bir rəngdə, qrafikdə başqa rəngdə görünürdü. İndi hər iki
  // blok eyni funksiyanı çağırır.
  //
  // `store-colors.js` index.html-də bu fayldan ƏVVƏL yüklənir; yenə də
  // yoxlayırıq ki, yüklənmə sırası dəyişsə qrafik səssizcə yalan rəngə düşməsin.
  function colorFor(name) {
    if (typeof StoreColors === "undefined") return TOKENS.accent;
    return STORE_COLORS[StoreColors.slot(name)];
  }

  let chart = null;

  // ---------------------------------------------------------------- qrafik

  async function loadGroups() {
    const box = sel("historySelect");
    try {
      const data = await (await fetch("/api/analytics/groups?limit=30")).json();
      if (!data.items.length) {
        sel("historyNote").innerHTML =
          `<div class="notice">Hələ qiymət yoxdur — əvvəlcə kataloq emal edin.</div>`;
        return;
      }
      box.innerHTML = data.items
        .map(
          (g) =>
            `<option value="${esc(g.group_key)}">${esc(g.label)} — ${g.observations} müşahidə, ${g.stores} market</option>`
        )
        .join("");
      drawHistory(data.items[0].group_key);
    } catch {
      sel("historyNote").innerHTML =
        `<div class="notice error">Məhsul siyahısı yüklənmədi.</div>`;
    }
  }

  async function drawHistory(groupKey) {
    const note = sel("historyNote");
    let data;
    try {
      data = await (
        await fetch("/api/analytics/history?group_key=" + encodeURIComponent(groupKey))
      ).json();
    } catch {
      note.innerHTML = `<div class="notice error">Tarixçə yüklənmədi.</div>`;
      return;
    }

    if (!data.points.length) {
      note.innerHTML = `<div class="notice">Bu məhsul üçün müşahidə yoxdur.</div>`;
      return;
    }

    // Xanalar ÇƏKİLİŞDƏN ƏVVƏL paylanır - qrafik, leqenda və cədvəl eyni
    // paylanmanı görsün (bax `store-colors.js`).
    if (typeof StoreColors !== "undefined") StoreColors.note(data.stores);

    // Hər marketdə neçə müşahidə var? Qrafikin növü buna görə seçilir.
    const perStore = {};
    for (const p of data.points) perStore[p.store] = (perStore[p.store] || 0) + 1;
    const maxPerStore = Math.max(...Object.values(perStore));

    // TREND yalnız EYNİ marketin ən azı 2 müşahidəsi olanda mövcuddur.
    //
    // Niyə bu qədər vacibdir? Əks halda qrafik YALAN danışır: iki fərqli
    // marketin qiymətini zaman oxunda göstərsək, sanki qiymət 20 dəqiqədə
    // düşüb - halbuki bu, sadəcə iki kataloqun fərqli vaxtda emal edilməsidir.
    // Seyrək datada doğru vizual - marketlərin yan-yana müqayisəsidir.
    const hasTrend = maxPerStore >= 2;

    note.innerHTML = `<div class="notice">
      ${esc(data.label)} ${esc(data.size || "")} — ${data.points.length} müşahidə,
      ${data.stores.length} market.
      ${hasTrend ? "" : "Eyni marketdən 2 müşahidə olmadığı üçün trend yox, " +
        "<strong>market müqayisəsi</strong> göstərilir."}
    </div>`;

    if (typeof Chart === "undefined") {
      note.innerHTML += `<div class="notice warn">
        Qrafik kitabxanası yüklənmədi (internet yoxdur?) — rəqəmlər aşağıdakı
        cədvəldədir.
      </div>`;
      renderTable(data);
      return;
    }

    renderSummary(data);
    if (chart) chart.destroy();
    chart = hasTrend ? trendChart(data) : comparisonChart(data);
    renderTable(data);
  }

  /**
   * Qrafikin ÜSTÜNDƏKİ əsas rəqəm.
   *
   * Niyə? İstifadəçilərin çoxu qrafiki oxumur - onlara "indi ən ucuz neçəyədir?"
   * lazımdır. Rəqəm REAL datadan gəlir: müşahidələr arasında ən aşağı qiymət
   * və onun marketi. Uydurma trend faizi YAZILMIR - seyrək datada o, yalan
   * olardı (bax: aşağıdakı `hasTrend` izahı).
   */
  function renderSummary(data) {
    const box = sel("chartSummary");
    if (!box) return;

    const cheapest = data.points.reduce((a, b) => (b.price < a.price ? b : a));
    box.innerHTML = `
      <span class="chart-value">${cheapest.price.toFixed(2)}<span class="cur">₼</span></span>
      <span class="chart-caption">ən aşağı müşahidə — ${esc(cheapest.store)}</span>`;
  }

  // Ümumi ayarlar - iki qrafik növü arasında fərq yalnız məlumatdadır.
  // Şəbəkə xətləri çox soluqdur (8%): onlar oxunu oxumağa kömək etməlidir,
  // diqqəti sütunlardan yayındırmamalı.
  const baseOptions = (yTitle) => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 260 },
    layout: { padding: { top: 4 } },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: TOKENS.text,
        titleColor: TOKENS.surface,
        bodyColor: TOKENS.surface,
        padding: 10,
        cornerRadius: 8,
        displayColors: false,
        titleFont: { size: 12, weight: "600" },
        bodyFont: { size: 13 },
        callbacks: { label: (ctx) => `${ctx.parsed.y ?? ctx.parsed}: ` },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        border: { color: alpha(TOKENS.text, 0.12) },
        ticks: { color: TOKENS.text2, font: { size: 12 } },
      },
      y: {
        title: { display: true, text: yTitle, color: TOKENS.text2, font: { size: 11 } },
        // Sıfırdan başlamır: ərzaq qiymətlərində fərq kiçikdir və
        // sıfırdan başlayan ox onu görünməz edir.
        beginAtZero: false,
        grid: { color: alpha(TOKENS.text, 0.08), drawTicks: false },
        border: { display: false },
        ticks: { color: TOKENS.text2, font: { size: 12 }, padding: 8 },
      },
    },
  });

  function comparisonChart(data) {
    // Hər marketin ƏN SON qiyməti
    const latest = {};
    for (const p of data.points) latest[p.store] = p;
    const stores = Object.keys(latest);
    const values = stores.map((s) => latest[s].price);

    // Burada rəng SABİT market rəngi DEYİL, məna daşıyır: ən ucuz - yaşıl,
    // qalanları - accent. Səbəb odur ki, bu qrafikdə leqenda yoxdur, market
    // adları onsuz da oxun altındadır; rəngi "ən ucuz hansıdır?" sualına
    // sərf etmək daha faydalıdır. Trend qrafikində isə əksinə - orada
    // leqenda var və rəng marketi tanıdır.
    const min = Math.min(...values);
    const fill = values.map((v, i) =>
      v === min ? TOKENS.green : alpha(colorFor(stores[i]), 0.75)
    );
    const hover = values.map((v, i) =>
      v === min ? TOKENS.green : colorFor(stores[i])
    );

    const options = baseOptions("AZN");
    options.plugins.tooltip.callbacks.label = (ctx) =>
      `${ctx.parsed.y.toFixed(2)} AZN` + (ctx.parsed.y === min ? " — ən ucuz" : "");

    // Sütunlar arasındakı fərq görünsün deyə oxu bir az aşağıdan başladırıq
    const pad = Math.max(0.1, (Math.max(...values) - min) * 0.5);
    options.scales.y.min = Math.max(0, min - pad);
    options.scales.y.max = Math.max(...values) + pad;

    return new Chart(sel("historyChart"), {
      type: "bar",
      data: {
        labels: stores,
        datasets: [{
          data: values,
          backgroundColor: fill,
          hoverBackgroundColor: hover,
          borderRadius: 6,
          borderSkipped: false,
          maxBarThickness: 84,
        }],
      },
      options,
    });
  }

  function trendChart(data) {
    const options = baseOptions("AZN");
    options.plugins.legend.display = true;
    options.plugins.legend.position = "bottom";
    options.plugins.legend.labels = {
      color: TOKENS.text2,
      usePointStyle: true,
      pointStyle: "circle",
      boxWidth: 7,
      padding: 16,
      font: { size: 12 },
    };
    options.interaction = { mode: "nearest", intersect: false };
    options.plugins.tooltip.displayColors = true;
    options.plugins.tooltip.callbacks.label = (ctx) =>
      `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} AZN`;

    const labels = [...new Set(data.points.map((p) => p.seen_at.slice(0, 16)))].sort();
    const datasets = data.stores.map((store) => ({
      label: store,
      data: data.points
        .filter((p) => p.store === store)
        .map((p) => ({ x: p.seen_at.slice(0, 16), y: p.price })),
      borderColor: colorFor(store),
      backgroundColor: colorFor(store),
      borderWidth: 2,
      tension: 0.25,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: TOKENS.surface,
      pointBorderWidth: 2,
      spanGaps: true,
    }));

    return new Chart(sel("historyChart"), {
      type: "line",
      data: { labels, datasets },
      options,
    });
  }

  function renderTable(data) {
    sel("historyTable").innerHTML =
      `<thead><tr>
         <th scope="col">Market</th><th scope="col" class="num">Qiymət</th>
         <th scope="col" class="num">Köhnə</th><th scope="col" class="num">Vahid qiymət</th>
         <th scope="col">Tarix</th>
       </tr></thead><tbody>` +
      data.points
        .map(
          (p) => `<tr>
            <td class="txt">${esc(p.store)}</td>
            <td class="num"><strong>${p.price.toFixed(2)}</strong></td>
            <td class="num old">${p.old_price ? p.old_price.toFixed(2) : ""}</td>
            <td class="num">${p.unit_price ? p.unit_price.toFixed(2) : "—"}</td>
            <td class="txt">${esc(p.seen_at)}</td>
          </tr>`
        )
        .join("") +
      `</tbody>`;
  }

  // ---------------------------------------------------------------- endirimlər

  // ---------------------------------------------------------------- istisnalar
  //
  // "Endirim yoxlaması" tətbiqin ƏN GÜCLÜ fərqləndirici funksiyasıdır: kataloq
  // "köhnə qiymət" iddiası edir, biz onu öz müşahidələrimizlə tutuşduruq.
  // Ona görə burada EXCEPTION-FIRST məntiq var - diqqət tələb edən sətirlər
  // yuxarıda, təsdiqlənmişlər aşağıda.

  // Hökm -> vizual siniflər. Əvvəl bu, şablon sətrinin içində iç-içə ternary
  // idi və oxunmurdu; cədvəl həm qısadır, həm də yeni hökm əlavə etmək asandır.
  //
  // `rank` sıralama üçündür: kiçik rəqəm = daha çox diqqət tələb edir.
  const VERDICT = {
    subheli:        { rank: 0, row: "is-bad",  pill: "is-red" },
    tesdiqlenmeyib: { rank: 1, row: "is-warn", pill: "is-amber" },
    endirim_yoxdur: { rank: 2, row: "",        pill: "" },
    tesdiqlenib:    { rank: 3, row: "is-ok",   pill: "is-green" },
  };

  const verdictStyle = (v) => VERDICT[v] || { rank: 2, row: "", pill: "" };

  async function loadDiscounts() {
    const box = sel("discountList");
    let data;
    try {
      data = await (await fetch("/api/analytics/discounts?limit=50")).json();
    } catch {
      box.innerHTML = `<div class="notice error">Endirim yoxlaması yüklənmədi.</div>`;
      return;
    }

    if (!data.with_discount_claim) {
      box.innerHTML = `<div class="notice">
        Yoxlanan ${data.total_checked} qiymət sətrində endirim iddiası yoxdur
        (köhnə qiymət göstərilməyib).
      </div>`;
      return;
    }

    const c = data.counts || {};
    const counters = `
      <div class="counter-row">
        <span class="pill is-red">Şübhəli ${c.subheli || 0}</span>
        <span class="pill is-amber">Təsdiqlənməyib ${c.tesdiqlenmeyib || 0}</span>
        <span class="pill is-green">Təsdiqlənib ${c.tesdiqlenib || 0}</span>
        <span class="pill">Yoxlanıldı ${data.with_discount_claim}</span>
      </div>`;

    // DİQQƏT TƏLƏB EDƏN ƏVVƏLDƏ. Sıra pozulmasın deyə `rank` bərabər olanda
    // orijinal sıra saxlanılır (Array.prototype.sort stabildir).
    const items = [...data.items].sort(
      (a, b) => verdictStyle(a.verdict).rank - verdictStyle(b.verdict).rank
    );

    const rows = items
      .map((item) => {
        const style = verdictStyle(item.verdict);
        // `verdict_label` backend-dən gəlir - eyni mətni iki yerdə saxlamırıq
        const label = esc(item.verdict_label || item.verdict);
        const why = (item.reasons || []).join(" · ");
        return `<div class="exception ${style.row}">
          <span class="pill ${style.pill}">${label}</span>
          <div class="exception-main">
            <div class="exception-title">${esc(item.label)}</div>
            <div class="exception-why">${esc(item.store)}${why ? " — " + esc(why) : ""}</div>
          </div>
          <div class="exception-price">
            <div class="exception-now">${item.price.toFixed(2)}<span class="cur">₼</span></div>
            <div class="exception-was">${item.old_price.toFixed(2)} ₼ · −${item.discount_pct}%</div>
          </div>
        </div>`;
      })
      .join("");

    box.innerHTML = counters + `<div class="exception-list">${rows}</div>`;
  }

  sel("historySelect").addEventListener("change", (e) => drawHistory(e.target.value));
  sel("discountRefresh").addEventListener("click", loadDiscounts);

  loadGroups();
  loadDiscounts();
})();
