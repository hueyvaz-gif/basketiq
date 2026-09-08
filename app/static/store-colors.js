// Market -> palitra xanası. BU FAYL YEGANƏ MƏNBƏDİR.
//
// Həm cədvəl/barlar (`app.js`), həm qrafik (`analytics.js`) buradan soruşur.
// İkinci reyestr saxlamırıq: əvvəl `app.js` API sırası, `analytics.js` isə
// əlifba sırası ilə öz Map-ini doldururdu və eyni market cədvəldə bir,
// qrafikdə başqa rəngdə görünürdü.
//
// ---------------------------------------------------------------- yanaşma
//
// Tələb ikiqatdır və tək hash bunların ikisini birdən vermir:
//   1. rəng SIRAYA yox, ADA bağlı olsun — `app/api/basket.py` marketləri səbət
//      cəminə görə çeşidləyir, yəni səbətə bir məhsul əlavə edən kimi sıra
//      dəyişir; rəng dəyişməməlidir;
//   2. fərqli marketlər fərqli rəng alsın — leqendada iki eyni nöqtə olsa,
//      leqenda mənasını itirir.
//
// Təmiz djb2 hash 2-ni pozur: ölçdük, real 6 market adı
// (Test Market, Bravo, Araz, Kənar Market, Araz Market, Test Scrape Market)
// 6 xanadan yalnız 3-nə düşürdü — xana 5-də DÖRD ad birdən:
//   Araz:1  Araz Market:3  Test Market:5  Bravo:5  Kənar Market:5  Test Scrape Market:5
//
// Ona görə: hash XANANI TƏKLİF EDİR, toqquşma isə xətti sınaqla (linear
// probing) həll olunur. Sınaq marketlərin ƏLİFBA sırasında aparılır — əlifba
// backend-in qaytardığı sıradan asılı olmadığı üçün nəticə giriş sırasından
// asılı deyil. `sort()` qəsdən `localeCompare`-siz çağırılır: locale brauzerə
// görə dəyişir, bu isə eyni datada fərqli rəng deməkdir.
//
// MARKETLƏR DƏSTİ DƏYİŞƏNDƏ NƏ OLUR?
//   - yeni marketin təklif etdiyi xana boşdursa — heç kimin rəngi dəyişmir
//     (hər ad öz hash xanasını alır, qonşulardan asılı deyil);
//   - toqquşma varsa — həmin toqquşma zəncirindəki marketlərin xanaları
//     yenidən paylanır. Yəni sabitlik zəmanətli deyil, amma pozulma
//     toqquşma ilə məhdudur, `Map.size` variantındakı kimi hər dəfə deyil.
//   - 6-dan çox market olsa toqquşma riyazi olaraq qaçılmazdır: 7-ci və sonrakı
//     adlar öz hash xanasını (təkrar) alır. Uydurma 7-ci rəng çıxarmırıq.

(() => {
  const COUNT = 6;

  // Görülmüş bütün market adları. Xanalar bu DƏSTİN funksiyasıdır —
  // adların gəlmə SIRASININ yox.
  const known = new Set();
  let slots = new Map();

  /** djb2 — qısa, sabit, kitabxanasız. Yalnız xana TƏKLİF edir. */
  function hash(name) {
    const s = String(name ?? "");
    let h = 5381;
    for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
    return h % COUNT;
  }

  function rebuild() {
    const names = [...known].sort();
    const taken = new Array(COUNT).fill(false);
    const next = new Map();

    for (const name of names) {
      const start = hash(name);
      let step = 0;
      while (step < COUNT && taken[(start + step) % COUNT]) step++;
      // step === COUNT: bütün xanalar doludur (7+ market) -> hash xanası təkrarlanır
      const slot = step < COUNT ? (start + step) % COUNT : start;
      if (step < COUNT) taken[slot] = true;
      next.set(name, slot);
    }
    slots = next;
  }

  /**
   * Adları əvvəlcədən elan edir.
   *
   * Render başlamazdan ƏVVƏL çağırılır ki, sətirlər çəkilərkən dəst böyüyüb
   * artıq çəkilmiş sətirlərin rəngini köhnəltməsin.
   */
  function note(names) {
    let grew = false;
    for (const name of names || []) {
      const key = String(name ?? "");
      if (!known.has(key)) {
        known.add(key);
        grew = true;
      }
    }
    if (grew) rebuild();
  }

  /** Ad -> 0..5. Tanınmayan ad sükutla yanlış rəng almasın deyə özü qeydə düşür. */
  function slot(name) {
    const key = String(name ?? "");
    if (!slots.has(key)) note([key]);
    return slots.get(key);
  }

  /** Ad -> CSS dəyişəni (`--store-1..6`). */
  function cssVar(name) {
    return `var(--store-${slot(name) + 1})`;
  }

  // `globalThis`: brauzerdə `window`, test mühitində (node) isə qlobal obyekt.
  globalThis.StoreColors = { note, slot, cssVar, COUNT };
})();
