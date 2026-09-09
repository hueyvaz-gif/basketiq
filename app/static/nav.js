// İstifadəçi / Admin paneli arasında keçid.
//
// NİYƏ AYRICA FAYL?
// Naviqasiya heç bir data axınından asılı deyil - nə API çağırır, nə də
// render edir. app.js-in içində olsaydı, upload məntiqi qırılanda tab da
// işləməzdi. Ayrı fayl bu asılılığı ümumiyyətlə yaratmır.
//
// NİYƏ HƏR İKİ PANEL DOM-DADIR (yalnız biri gizlidir)?
// Digər skriptlər yüklənəndə `getElementById(...).addEventListener(...)`
// çağırır. Panel DOM-da olmasaydı, həmin sətirlər `null`-a düşüb bütün
// faylı qırardı. Gizlətmək `display:none`-dur - element mövcuddur, sadəcə
// görünmür və ekran oxuyucusu da onu keçir.

(() => {
  const tabs = [...document.querySelectorAll(".seg-btn[data-panel]")];
  const panels = {
    user: document.getElementById("panel-user"),
    admin: document.getElementById("panel-admin"),
  };

  function show(name) {
    for (const tab of tabs) {
      const active = tab.dataset.panel === name;
      tab.setAttribute("aria-selected", active ? "true" : "false");
      // tabindex: klaviatura ilə Tab basanda yalnız AKTİV tab-a düşülür,
      // qruplar arasında isə ox düymələri ilə gəzilir (ARIA tab pattern).
      tab.tabIndex = active ? 0 : -1;
    }
    for (const [key, panel] of Object.entries(panels)) {
      if (panel) panel.classList.toggle("hidden", key !== name);
    }
    // Hash saxlanılır ki, səhifə yenilənəndə eyni panel açılsın -
    // admin panelində işləyərkən hər F5-dən sonra tab axtarmaq lazım gəlməsin.
    if (location.hash.slice(1) !== name) history.replaceState(null, "", "#" + name);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => show(tab.dataset.panel));

    tab.addEventListener("keydown", (e) => {
      const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      e.preventDefault();
      const next = tabs[(index + step + tabs.length) % tabs.length];
      next.focus();
      show(next.dataset.panel);
    });
  });

  // Defolt İSTİFADƏÇİ panelidir. Admin yalnız açıq şəkildə soruşulanda açılır.
  show(location.hash.slice(1) === "admin" ? "admin" : "user");

  /**
   * ADMİN TABI SERVERİN QƏRARINA TABEDİR (B11).
   *
   * `ADMIN_ENABLED` bağlıdırsa, admin endpoint-ləri onsuz da 404 verir -
   * tab isə qalsaydı, istifadəçi açıb yalnız xəta mesajları görərdi.
   *
   * BU, TƏHLÜKƏSİZLİK QATI DEYİL. Statik HTML hər halda brauzerə gedir;
   * gizlətmək səliqədir, qapı isə serverdədir (`app/security.py`). Ona görə
   * sorğu uğursuz olsa da heç nə pozulmur: tab qalır, arxasındakı endpoint
   * yenə bağlıdır.
   *
   * PANEL DOM-DAN SİLİNMİR - yuxarıdakı səbəb: digər skriptlər yükləndiyi
   * anda öz elementlərini axtarır və `null` üzərində qırılardı.
   */
  async function gateAdmin() {
    try {
      const { enabled } = await (await fetch("/api/admin/state")).json();
      if (enabled) return;
      const tab = document.getElementById("tabAdmin");
      if (tab) tab.hidden = true;
      if (location.hash.slice(1) === "admin") show("user");
    } catch {
      /* cavab gəlmədi - tab olduğu kimi qalır */
    }
  }

  gateAdmin();
})();
