// REKLAM SLOTU (E19/E20/E23) — ana səhifədəki satıla bilən yer.
//
// ÜÇ QAYDA:
//
// 1. REKLAM ENDİRİMƏ BƏNZƏMİR. Sayt qiymət müqayisəsi vəd edir; sponsorlu
//    kart real endirimlə qarışsaydı, saytın yeganə dəyəri - etibar - itərdi.
//    Ona görə kart ayrı formadadır və üstündə «Reklam» nişanı var.
//
// 2. BOŞ SLOT GİZLƏNMİR, SATILIR (E20). Sifariş yoxdursa, yerə «Sizin
//    reklamınız burada ola bilər» yazılır. Boş yeri gizlətmək inventarı
//    görünməz edir; ən yaxşı satıcı elə yerin özüdür.
//    İSTİSNA: yan lövhə və məzmun içindəki dar ekran qutusu (`data-hide-empty`)
//    boş olanda GİZLƏNİR - aşağıda `boşdaGizlənir`.
//
// 3. KEÇİD ADİ `<a href>`-DİR. Klik serverdə sayılır (`/api/ads/{id}/click`
//    yönləndirir), yəni JS sönük olsa da həm reklam işləyir, həm hesabat.
//    Sayğac JS-ə bağlansaydı, reklamverənin rəqəmi istifadəçinin brauzer
//    ayarından asılı olardı. «Ətraflı →» düyməsi də AYRICA keçid deyil -
//    həmin `<a>`-nın içindəki `span`-dır: klik izləmə tək yoldan keçir.
//
// GÖSTƏRİM = GÖRÜNƏ BİLƏN QUTUYA GÖNDƏRİLMİŞ REKLAM (2026-09-11).
// Server göstərimi `/api/ads/slot/...` sorğusunda sayır. Əvvəl HƏR qutu
// üçün sorğu gedirdi və iki yerdə hesabat şişirdi (jurnalda ölçüldü):
//   - yan lövhə 1440px-dən dar ekranda CSS ilə gizlidir, amma sorğu yenə
//     gedirdi - adi noutbukda heç kimin görmədiyi reklama göstərim yazılırdı;
//   - dil dəyişəndə bütün qutular yenidən soruşulurdu - hər dil dəyişikliyi
//     bir göstərim daha idi.
// İndi: gizli qutu sorğu göndərmir, dil dəyişəndə yalnız mətn yenidən çəkilir,
// ekran genişlənib lövhə görünən kimi o, BİR dəfə yüklənir.
//
// EYNİ SLOT İKİ QUTUDA: sol lövhə və dar ekran qutusu (`.ad-inline`) eyni
// `home-rail-left` slotunu göstərir. CSS onları bir-birinin dəqiq əksi edir -
// hər enində yalnız biri görünür, yəni yalnız biri soruşulur.
//
// CANLI KART (2026-09-11): dolu reklam `.is-live` alır - aurora fonu, şüşə
// mətn bloku, nadir parıltı, hover-də qalxma. Bütün hərəkət CSS-dədir və
// YALNIZ transform/opacity işlədir (style.css, «CANLI REKLAM KARTI»). Burada
// iki iş var: kart görünüş sahəsinə girəndə `.is-visible` alır, çıxanda isə
// `.is-offscreen` - onda animasiya dayanır.

(() => {
  // BİR SLOT DEYİL, HAMISI. Əvvəl yalnız `#adSlot` doldurulurdu; yan
  // lövhələr əlavə olunanda ikinci nüsxə yazmaq lazım gələrdi və biri
  // dəyişəndə digəri köhnə qalardı. İndi `data-slot` daşıyan hər element
  // eyni məntiqlə doldurulur - yeni yer əlavə etmək = HTML-də bir sətir.
  const boxes = [...document.querySelectorAll("[data-slot]")];
  if (!boxes.length) return;

  // Qutu → son cavab. Dil dəyişəndə kart buradan yenidən çəkilir, serverə
  // sorğu getmir. `null` = sorğu yoldadır (eyni qutu üçün ikinci sorğu getməsin).
  const cache = new Map();

  // GÖRÜNMƏ brauzerin özündən soruşulur: 1440px həddi CSS-dədir
  // (`.ad-rail` / `.ad-inline`) və burada ikinci nüsxəsi yazılmır -
  // hədd dəyişəndə JS köhnə rəqəmlə qalardı.
  const görünür = (box) => getComputedStyle(box).display !== "none";

  // BOŞ OLANDA GİZLƏNƏN QUTULAR.
  // Yan lövhə səhifənin kənarındadır - boş qutu orada sadəcə sınmış görünür.
  // Dar ekran qutusu (`data-hide-empty`) isə məzmunun ORTASINDADIR: boş
  // olanda «reklam yeri satılır» kartı göstərsəydi, 2026-09-10-da götürülən
  // sətir arası banner geri qayıtmış olardı.
  const boşdaGizlənir = (box) =>
    box.classList.contains("ad-rail") || box.hasAttribute("data-hide-empty");

  // --- Görünəndə peyda olma + ekrandan çıxanda dayanma --------------------
  //
  // IntersectionObserver: kart görünüş sahəsinə girəndə `.is-visible` alır,
  // keçidi CSS edir (transform + opacity). Scroll hadisəsinə qulaq asmırıq -
  // hər piksel sürüşmədə hesablama olardı.
  //
  // MÜŞAHİDƏ PEYDA OLANDAN SONRA DA DAVAM EDİR: kart ekrandan çıxanda
  // `.is-offscreen` alır və aurora/parıltı dayanır - görünməyən yerdə GPU
  // yanmasın (dizayn auditi: əvvəl kart aşağı sürüşdürüləndə də hərəkət edirdi).
  //
  // AZ HƏRƏKƏT rejimində və ya köhnə brauzerdə müşahidəçi YOXDUR: kart
  // dərhal görünür. Gözləmə vəziyyətində ilişib qalan görünməz reklam
  // həm istifadəçiyə, həm reklamverənə haqsızlıq olardı.
  const azHərəkət = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const göstər = (card) => card.classList.add("is-visible");
  const izləyici =
    "IntersectionObserver" in window && !azHərəkət
      ? new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              const card = entry.target;
              card.classList.toggle("is-offscreen", !entry.isIntersecting);
              if (!entry.isIntersecting) continue;
              göstər(card);
              card.closest("[data-slot]").dataset.revealed = "1";
            }
          },
          { threshold: 0.2 }
        )
      : null;

  function canlandır(box) {
    const card = box.querySelector(".ad-card.is-live");
    if (!card) return;
    if (!izləyici) {
      göstər(card);
      return;
    }
    // Dil dəyişəndə kart yenidən çəkilir - artıq görünmüş kart ikinci dəfə
    // «peyda olmasın», olduğu yerdə qalsın. Müşahidə isə HƏR kartda qalır.
    if (box.dataset.revealed === "1") göstər(card);
    izləyici.observe(card);
  }

  function dolu(ad) {
    const şəkil = ad.image
      ? `<span class="ad-media"><img class="ad-image" src="${esc(ad.image)}" alt="" loading="lazy"></span>`
      : "";

    // `rel="sponsored nofollow noopener"`: axtarış sistemlərinə keçidin
    // ödənişli olduğunu bildirir - bu, reklamın gizlədilməməsi qaydasının
    // texniki tərəfidir. `.ad-bg` (aurora) və `.ad-shine` (parıltı, məzmunun
    // ÜSTÜNDƏ) yalnız dekordur - ekran oxuyucusundan gizlidir.
    return `<a class="ad-card is-live" href="/api/ads/${ad.id}/click"
               target="_blank" rel="sponsored nofollow noopener">
        <span class="ad-bg" aria-hidden="true"></span>
        <span class="ad-flag">${esc(t("ads.sponsored"))}</span>
        ${şəkil}
        <span class="ad-body">
          <span class="ad-title">${esc(ad.title)}</span>
          ${ad.body ? `<span class="ad-text">${esc(ad.body)}</span>` : ""}
          <span class="ad-foot">
            <span class="ad-by">${esc(ad.advertiser)}</span>
            <span class="ad-cta">${esc(t("ads.more"))}<span class="ad-cta-arrow" aria-hidden="true">→</span></span>
          </span>
        </span>
        <span class="ad-shine" aria-hidden="true"></span>
      </a>`;
  }

  function boş(contact) {
    // Əlaqə ünvanı təyin olunmayıbsa, düymə GÖSTƏRİLMİR: işləməyən keçid
    // reklamverəni itirilmiş məktubla qoyar.
    const cta = contact
      ? `<a class="btn btn-secondary" href="mailto:${esc(contact)}?subject=${encodeURIComponent(
          t("ads.mailSubject")
        )}">${esc(t("ads.cta"))}</a>`
      : "";

    return `<div class="ad-card is-empty">
        <span class="ad-flag">${esc(t("ads.slotLabel"))}</span>
        <span class="ad-body">
          <span class="ad-title">${esc(t("ads.emptyTitle"))}</span>
          <span class="ad-text">${esc(t("ads.emptyBody"))}</span>
        </span>
        ${cta}
      </div>`;
  }

  function render(box, data) {
    // Köhnə kart DOM-dan çıxmazdan əvvəl müşahidədən də çıxır - əks halda
    // hər dil dəyişikliyi müşahidəçidə «ölü» element saxlayardı.
    const köhnə = box.querySelector(".ad-card.is-live");
    if (köhnə && izləyici) izləyici.unobserve(köhnə);

    box.innerHTML = data.ad ? dolu(data.ad) : boş(data.contact);
    if (boşdaGizlənir(box)) {
      box.hidden = !data.ad;
    }
    canlandır(box);
  }

  async function loadOne(box) {
    // Artıq yüklənib (və ya yoldadır), yaxud indi görünmür - sorğu YOX.
    // Görünməyən qutuya sorğu göndərmək heç kimin görmədiyi reklama
    // göstərim yazmaq deməkdir (yuxarıdakı qeydə bax).
    if (cache.has(box) || !görünür(box)) return;
    cache.set(box, null);

    const slot = box.dataset.slot || "home-banner";
    try {
      const res = await fetch(`/api/ads/slot/${encodeURIComponent(slot)}`);
      if (!res.ok) throw new Error("http");
      const data = await res.json();
      cache.set(box, data);
      render(box, data);
    } catch {
      // Reklam qatı səhifənin qalanını qırmamalıdır: slot sadəcə boş qalır.
      // Keşdən çıxarılır - növbəti fürsətdə (ekran dəyişəndə) yenidən sınanır.
      cache.delete(box);
      box.innerHTML = "";
      if (boşdaGizlənir(box)) box.hidden = true;
    }
  }

  const loadVisible = () => boxes.forEach(loadOne);

  loadVisible();

  // Pəncərə genişlənib lövhə GÖRÜNƏN kimi bir dəfə yüklənir (daralanda isə
  // dar ekran qutusu). `resize` saniyədə onlarla dəfə gəlir - son hərəkətdən
  // sonra yoxlanılır.
  let gözlə = null;
  window.addEventListener("resize", () => {
    clearTimeout(gözlə);
    gözlə = setTimeout(loadVisible, 200);
  });

  // Dil dəyişəndə YALNIZ MƏTN yenidən çəkilir - serverə sorğu getmir,
  // yəni dil dəyişikliyi göstərim sayılmır.
  document.addEventListener("basketiq:lang", () => {
    for (const [box, data] of cache) {
      if (data) render(box, data);
    }
  });
})();
