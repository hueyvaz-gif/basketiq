// AI tövsiyəsi — SSE ilə token-token axan mətn.
//
// Niyə fetch + ReadableStream, EventSource deyil? EventSource yalnız GET-i
// dəstəkləyir və xəta idarəsi zəifdir. fetch ilə axını özümüz oxuyuruq və
// server bağlayanda dəqiq bilirik.
//
// DÜŞÜNMƏ FİLTRİ BURADA DEYİL. Model bəzən cavabdan əvvəl öz-özü ilə danışır
// (`<think>...`). O mətn BACKEND-də - `ai/sanitize.py`-də - kəsilir və brauzerə
// heç vaxt çatmır. Frontend-də filtrləmək səhv olardı: xam mətn artıq
// şəbəkədən keçmiş, brauzerin yaddaşına düşmüş olardı.

let adviseController = null;

function advisorEl(id) {
  return document.getElementById(id);
}

document.getElementById("adviseBtn").addEventListener("click", async () => {
  const textEl = advisorEl("advisorText");
  const checkEl = advisorEl("advisorCheck");
  const placeholder = advisorEl("advisorPlaceholder");
  const btn = advisorEl("adviseBtn");

  advisorEl("factsBox").classList.add("hidden");
  placeholder.classList.add("hidden");
  textEl.innerHTML = "";
  textEl.classList.add("typing");
  checkEl.innerHTML = "";
  btn.disabled = true;
  btn.textContent = t("advisor.writing");

  adviseController = new AbortController();

  try {
    const res = await fetch("/api/basket/advise", { signal: adviseController.signal });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE mesajları boş sətirlə ayrılır
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;

        let payload;
        try {
          payload = JSON.parse(line.slice(5).trim());
        } catch {
          continue;
        }

        if (payload.type === "token") {
          // Axın gedərkən DÜZ MƏTN yazılır (textContent), HTML yox.
          // Vurğulama yalnız sonda edilir - bax: aşağıdakı "done" bloku.
          textEl.textContent += payload.text;
        } else if (payload.type === "error") {
          // Texniki mətn istifadəçiyə göstərilmir - konsola yazılır.
          console.error("[advisor]", payload.text);
          showUnavailable(checkEl, placeholder);
        } else if (payload.type === "done") {
          // Backend TAM mətnin son təmiz versiyasını göndərir.
          //
          // Niyə əvəz edirik? Axın filtri mətni hissə-hissə görür və
          // "Cavab:" kimi son-cavab markerini yalnız mətn bitəndə tanımaq
          // olur. Ona qədər ekranda artıq nəsə var. Adətən iki versiya
          // eynidir və heç nə görünmür; fərq varsa - təmizi qalır.
          if (payload.text) textEl.textContent = payload.text;

          // İndi vurğulaya bilərik. Axın GEDƏRKƏN etmək olmazdı: yarımçıq
          // rəqəm ("2.4") vurğulanıb sonra dəyişərdi və mətn gözün
          // qarşısında titrəyərdi.
          highlight(textEl);
          renderCheck(checkEl, payload.check);
        }
      }
    }

    // Model heç nə yazmayıbsa boş kart qalmasın
    if (!textEl.textContent.trim()) showUnavailable(checkEl, placeholder);
  } catch (e) {
    if (e.name !== "AbortError") {
      console.error("[advisor]", e);
      showUnavailable(checkEl, placeholder);
    }
  } finally {
    textEl.classList.remove("typing");
    btn.disabled = false;
    btn.innerHTML =
      `<svg aria-hidden="true"><use href="#icon-sparkle"></use></svg> ${t("ai.get")}`;
  }
});

/** Regexp-də xüsusi mənası olan simvolları zərərsizləşdirir. */
function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

/**
 * Tövsiyə mətnində ƏSAS dəyərləri vurğulayır: məbləğlər və qalib marketin adı.
 *
 * NİYƏ textContent-dən HTML qururuq?
 * Mətn modeldən gəlir, yəni ona etibar etmək olmaz. Əvvəlcə `textContent`
 * oxunur və `escapeHtml` ilə tam qaçırılır, SONRA yalnız öz `<mark>`
 * etiketlərimiz əlavə olunur. Beləliklə modelin yazdığı hər hansı `<script>`
 * sadəcə mətn kimi qalır - heç vaxt icra olunmur.
 *
 * Vurğulanan dəyərlər UYDURULMUR: məbləğ mətnin özündən, market adı isə
 * səhifədəki hero blokundan (yəni backend hesabından) götürülür.
 */
function highlight(el) {
  const text = el.textContent;
  if (!text.trim()) return;

  let html = escapeHtml(text);

  // 1. Məbləğlər: "19.65 AZN", "2,45 ₼", "3.80 manat".
  //    Valyuta vahidi MƏCBURİDİR (lookahead). Olmasaydı "2.5%" yağlılıq və
  //    ya "1.8 L" həcm də vurğulanardı - onlar isə məbləğ deyil.
  html = html.replace(
    /(^|[^\d.,])(\d+[.,]\d{1,2})(?=\s*(?:AZN|₼|manat))/gi,
    (_, before, amount) => `${before}<mark class="is-money">${amount}</mark>`
  );

  // 2. Qalib marketin adı.
  const winner = document.querySelector(".hero-store")?.textContent.trim();
  if (winner && winner.length > 1) {
    // `\b` ƏVƏZİNƏ "hərf olmayan simvol" işlədirik.
    //
    // Səbəb Azərbaycan dilindədir: şəkilçi ada yapışır — "Arazda", "Araza",
    // "Araz-a". `\bAraz\b` bunların heç birini tutmur, çünki addan sonra
    // hərf gəlir. Bu variant adın özünü tutur, şəkilçini isə vurğudan
    // kənarda saxlayır — yəni "Arazda" sözündə yalnız "Araz" işıqlanır.
    const safe = escapeRegExp(escapeHtml(winner));
    const pattern = new RegExp(`(^|[^\\p{L}])(${safe})`, "giu");
    html = html.replace(pattern, (_, before, name) => `${before}<mark>${name}</mark>`);
  }

  el.innerHTML = html;
}

/** İstifadəçi üçün nəzakətli hal - stack trace yox. */
function showUnavailable(checkEl, placeholder) {
  checkEl.innerHTML = `<div class="notice warn">
    AI tövsiyəsi hazırda əlçatan deyil. Müqayisə cədvəli işləməyə davam edir —
    ən ucuz market yuxarıda göstərilib.
  </div>`;
  placeholder.classList.add("hidden");
}

// Rəqəm yoxlaması: model faktlarda olmayan rəqəm yazıbsa, gizlətmirik - göstəririk.
function renderCheck(el, check) {
  if (!check) return;
  if (check.ok) {
    el.innerHTML = `<div class="notice ok">
      Yoxlanıldı: mətndəki ${check.checked} rəqəmin hamısı hesablanmış datadan gəlir.
    </div>`;
  } else {
    el.innerHTML = `<div class="notice warn">
      Diqqət: model datada olmayan rəqəm yazdı —
      <strong>${check.unknown_numbers.join(", ")}</strong>.
      Bu rəqəmlərə etibar etməyin.
    </div>`;
  }
}

// "Faktlara bax" — modelə nəyin göndərildiyini göstərir
document.getElementById("factsBtn").addEventListener("click", async () => {
  const box = advisorEl("factsBox");
  const btn = advisorEl("factsBtn");
  if (!box.classList.contains("hidden")) {
    box.classList.add("hidden");
    btn.setAttribute("aria-expanded", "false");
    return;
  }
  const data = await (await fetch("/api/basket/facts")).json();
  box.textContent = data.facts;
  box.classList.remove("hidden");
  btn.setAttribute("aria-expanded", "true");
});
