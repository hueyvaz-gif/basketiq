// İkon kitabxanasını (`icons.svg`) səhifəyə yükləyir.
//
// NİYƏ FAYLDAN, HTML-İN İÇİNDƏN DEYİL?
// İndi iki səhifə var: `index.html` və `product.html`. Sprite hər ikisinin
// içində yazılsaydı, 30 ikonun İKİ nüsxəsi olardı — kateqoriya ikonu
// dəyişəndə biri yenilənib digəri köhnə qalardı və heç bir yerdə xəta
// çıxmazdı (səhifə sadəcə başqa ikon göstərərdi).
//
// NİYƏ `<use href="icons.svg#icon-x">` DEYİL?
// Xarici fayla birbaşa `<use>` istinadı Safari-də İŞLƏMİR - ikonların yeri
// sükutla boş qalır. Faylı oxuyub səhifəyə salmaq bütün brauzerlərdə işləyir.
//
// GEC GƏLƏN SPRITE PROBLEMİ VƏ HƏLLİ:
// Fayl şəbəkədən gəldiyi üçün səhifədəki `<use href="#icon-x">` elementləri
// sprite hazır olmamışdan ƏVVƏL çəkilir. Brauzerlərin bir hissəsi hədəf
// element sonradan əlavə olunanda istinadı yenidən həll edir, bir hissəsi
// isə YOX - və fərq yalnız real brauzerdə görünür. Ona görə istinadları ƏL
// İLƏ yeniləyirik: `href`-i silib eyni dəyərlə geri yazmaq brauzeri
// istinadı yenidən həll etməyə məcbur edir. Bu, hər brauzerdə eyni işləyir.
//
// `window.IconsReady` promise-dir: JS ilə çəkilən səhifələr (məsələn
// `product.js`) render etməzdən əvvəl onu gözləyir.

window.IconsReady = (async () => {
  try {
    const res = await fetch("/static/icons.svg");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const markup = await res.text();

    const holder = document.createElement("div");
    holder.hidden = true;
    holder.innerHTML = markup;
    document.body.prepend(holder);

    // Sprite gələnə qədər çəkilmiş istinadları yenidən həll etdiririk.
    for (const use of document.querySelectorAll('use[href^="#icon-"]')) {
      const href = use.getAttribute("href");
      use.setAttribute("href", "");
      use.setAttribute("href", href);
    }
    return true;
  } catch (e) {
    // İkonsuz səhifə eybəcər görünür, amma İŞLƏYİR: bütün mətn və rəqəmlər
    // yerindədir. Ona görə burada səhifəni dayandırmırıq.
    console.error("[icons]", e);
    return false;
  }
})();
