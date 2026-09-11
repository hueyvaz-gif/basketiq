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
//
// 3. KEÇİD ADİ `<a href>`-DİR. Klik serverdə sayılır (`/api/ads/{id}/click`
//    yönləndirir), yəni JS sönük olsa da həm reklam işləyir, həm hesabat.
//    Sayğac JS-ə bağlansaydı, reklamverənin rəqəmi istifadəçinin brauzer
//    ayarından asılı olardı.
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
  // (`.ad-rail { display: none; }`) və burada ikinci nüsxəsi yazılmır -
  // hədd dəyişəndə JS köhnə rəqəmlə qalardı.
  const görünür = (box) => getComputedStyle(box).display !== "none";

  function dolu(ad) {
    const şəkil = ad.image
      ? `<img class="ad-image" src="${esc(ad.image)}" alt="" loading="lazy">`
      : "";

    // `rel="sponsored nofollow noopener"`: axtarış sistemlərinə keçidin
    // ödənişli olduğunu bildirir - bu, reklamın gizlədilməməsi qaydasının
    // texniki tərəfidir.
    return `<a class="ad-card" href="/api/ads/${ad.id}/click"
               target="_blank" rel="sponsored nofollow noopener">
        <span class="ad-flag">${esc(t("ads.sponsored"))}</span>
        ${şəkil}
        <span class="ad-body">
          <span class="ad-title">${esc(ad.title)}</span>
          ${ad.body ? `<span class="ad-text">${esc(ad.body)}</span>` : ""}
          <span class="ad-by">${esc(ad.advertiser)}</span>
        </span>
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
    box.innerHTML = data.ad ? dolu(data.ad) : boş(data.contact);
    // BOŞ LÖVHƏ GİZLƏNİR, BOŞ BANNER YOX.
    //
    // Fərq yerdədir: banner məzmun axınının içindədir və orada «bu yer
    // satılır» yazısı satıcı rolunu oynayır. Yan lövhə isə səhifənin
    // kənarındadır - orada boş qutu sadəcə sınmış görünür və heç kim
    // onu oxumur.
    if (box.classList.contains("ad-rail")) {
      box.hidden = !data.ad;
    }
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
      if (box.classList.contains("ad-rail")) box.hidden = true;
    }
  }

  const loadVisible = () => boxes.forEach(loadOne);

  loadVisible();

  // Pəncərə genişlənib lövhə GÖRÜNƏN kimi bir dəfə yüklənir. `resize`
  // saniyədə onlarla dəfə gəlir - son hərəkətdən sonra yoxlanılır.
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
