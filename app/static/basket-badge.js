// ÜST PANELDƏKİ SƏBƏT NİŞANI — hər səhifədə eyni.
//
// NİYƏ PAYLAŞILAN FAYL? Nişan dörd səhifədə də var və hamısında eyni sualı
// cavablandırır: «səbətimdə neçə məhsul var?». Hər səhifəyə öz nüsxəsini
// yazsaydıq, biri dəyişəndə digərləri köhnə qalardı - və səhv görünməz
// olardı, çünki rəqəm yenə də bir rəqəmdir, sadəcə yanlışdır.
//
// SƏBƏTƏ MƏHSUL ƏLAVƏ OLUNANDA DA YENİLƏNİR: `basketiq:basket` hadisəsi
// atılır (bax `ui.js:addToBasket`), nişan onu dinləyir. Səhifə yenilənmir.

(() => {
  const nişanlar = () => document.querySelectorAll("[data-basket-count]");
  if (!nişanlar().length) return;

  async function yenilə() {
    let say = 0;
    try {
      const data = await (await fetch("/api/basket")).json();
      // Nişan MƏHSUL sayını göstərir, ədəd sayını yox: «2» iki fərqli
      // məhsul deməkdir. Miqdar səbətin öz səhifəsindədir - üst paneldəki
      // kiçik rəqəm üçün «neçə sətir?» daha oxunaqlıdır.
      say = (data.items || []).length;
    } catch {
      return; // şəbəkə yoxdursa nişan olduğu kimi qalır
    }

    for (const el of nişanlar()) {
      const dəyişdi = el.textContent !== String(say);
      el.textContent = String(say);
      // Boş səbətdə rəqəm gizlənir: «0» nişanı hər səhifədə diqqət çəkər və
      // heç nə demir.
      el.hidden = say === 0;

      // QISA SIÇRAYIŞ (M2.5) - yalnız rəqəm DƏYİŞƏNDƏ.
      //
      // Səhifə açılışında da oynasaydı, hərəkət mənasını itirərdi: sıçrayış
      // «indicə nəsə əlavə olundu» deməkdir. Sinif animasiya bitəndə silinir,
      // əks halda ikinci əlavədə heç nə görünməzdi (eyni sinif təkrar
      // tətbiq olunanda brauzer animasiyanı yenidən başlatmır).
      if (dəyişdi && say > 0) {
        el.classList.remove("is-bumping");
        void el.offsetWidth;            // reflow - animasiyanı sıfırlayır
        el.classList.add("is-bumping");
        el.addEventListener("animationend", () => el.classList.remove("is-bumping"), {
          once: true,
        });
      }
    }
  }

  yenilə();
  document.addEventListener("basketiq:basket", yenilə);
})();
