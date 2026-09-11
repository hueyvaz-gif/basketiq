/* ============================================================================
   ÜÇ DİL: Azərbaycanca (defolt) · English · Русский

   NİYƏ SƏRVERDƏ YOX, BRAUZERDƏ?
   Səhifələr statikdir və server şablon motoru işlətmir. Dili brauzerdə
   dəyişmək o deməkdir ki, seçim ANİDİR - səhifə yenidən yüklənmir, sorğu
   getmir, server dəyişmir.

   AZƏRBAYCANCA MƏTN HTML-İN İÇİNDƏ QALIR.
   Hər elementdə həm `data-i18n` açarı, həm də azərbaycanca mətnin ÖZÜ var.
   Səbəb: JS işləməsə (yükləmə xətası, köhnə brauzer) səhifə boş qalmır -
   azərbaycanca oxunur. Tərcümə qatı YALNIZ üstünə yazır.

   DİNAMİK MƏTN NECƏ?
   `app.js`, `deals.js` və s. mətni JS-də qurur. Onlar `t("açar")` çağırır.
   Dil dəyişəndə `basketiq:lang` hadisəsi atılır və hər modul öz hissəsini
   yenidən çəkir - səhifəni yeniləmək lazım gəlmir.

   AÇAR ADLARI BÖLMƏYƏ GÖRƏDİR (`hero.*`, `admin.*`), çünki tərcüməni
   bölmə-bölmə yoxlamaq lazım gəlir; əlifba sırası bunu çətinləşdirərdi.
   ============================================================================ */

(() => {
  const STORAGE_KEY = "basketiq:lang";
  const SUPPORTED = ["az", "en", "ru"];

  const DICT = {
    // ====================================================== ÜMUMİ / NAVİQASİYA
    "common.loading": { az: "Yüklənir", en: "Loading", ru: "Загрузка" },
    "common.refresh": { az: "Yenilə", en: "Refresh", ru: "Обновить" },
    "common.product": { az: "Məhsul", en: "Product", ru: "Товар" },
    "common.products": { az: "Məhsullar", en: "Products", ru: "Товары" },
    "common.price": { az: "Qiymət", en: "Price", ru: "Цена" },
    "common.all": { az: "hamısı", en: "all", ru: "все" },
    "common.soon": { az: "Tezliklə", en: "Coming soon", ru: "Скоро" },
    "common.home": { az: "Ana səhifə", en: "Home", ru: "Главная" },
    "common.backToBasket": { az: "Səbətə qayıt", en: "Back to basket", ru: "Назад к корзине" },
    "common.delete": { az: "Sil", en: "Delete", ru: "Удалить" },
    "common.confirmDelete": { az: "Silinsin?", en: "Delete?", ru: "Удалить?" },
    "common.fineprint": {
      az: "Qiymətlər marketlərin dərc etdiyi həftəlik kataloqlardan götürülüb və filialda, eləcə də kataloqun qüvvədə olduğu müddətdən sonra fərqlənə bilər.",
      en: "Prices come from the weekly leaflets published by the supermarkets and may differ by branch, or after the leaflet expires.",
      ru: "Цены взяты из еженедельных каталогов магазинов и могут отличаться в филиале, а также после окончания срока действия каталога.",
    },

    // ------------------------------------------------------- SƏBƏT SƏHİFƏSİ (P1)
    "basket.mine": { az: "Səbətim", en: "My basket", ru: "Моя корзина" },
    "basket.add": { az: "Səbətə", en: "Add", ru: "В корзину" },
    "basket.added": { az: "Əlavə olundu", en: "Added", ru: "Добавлено" },
    "basket.addError": {
      az: "Əlavə olunmadı — yenidən yoxlayın.",
      en: "Could not add — try again.",
      ru: "Не добавлено — попробуйте снова.",
    },
    "basket.pageSub": {
      az: "Seçdiyiniz məhsullar, market üzrə cəm və hansı planın sərfəli olduğu.",
      en: "Your items, the total in each store, and which plan costs less.",
      ru: "Выбранные товары, сумма по каждому магазину и какой план выгоднее.",
    },
    "basket.items": { az: "Səbətdəki məhsullar", en: "Items in the basket", ru: "Товары в корзине" },
    "basket.totals": { az: "Market üzrə cəm", en: "Total per store", ru: "Сумма по магазинам" },
    "basket.totalsSub": {
      az: "Səbətin hamısını satan marketlər müqayisə olunur. Bir məhsulu satmayan market qalib seçilmir — cəmi az görünsə də.",
      en: "Only stores that sell every item are compared. A store missing an item cannot win — even if its total looks lower.",
      ru: "Сравниваются только магазины, где есть все товары. Магазин без одного товара не побеждает — даже если сумма меньше.",
    },
    "basket.plan": { az: "Tövsiyə olunan plan", en: "Recommended plan", ru: "Рекомендуемый план" },
    "basket.planSub": {
      az: "Plan yuxarıdakı səbətdən qidalanır — məhsul əlavə edin və ya silin, plan dərhal yenilənir.",
      en: "The plan is built from the basket above — add or remove an item and it updates at once.",
      ru: "План строится из корзины выше — добавьте или удалите товар, и он сразу обновится.",
    },
    "basket.planSingle": { az: "Tək market: {store}", en: "One store: {store}", ru: "Один магазин: {store}" },
    "basket.planSplit": { az: "{n} markete bölünmüş", en: "Split across {n} stores", ru: "Разделено на {n} магазина" },
    "basket.splitSaving": {
      az: "{n} markete getsəniz qənaət",
      en: "Saved by visiting {n} stores",
      ru: "Экономия при {n} магазинах",
    },
    "basket.cheapest": { az: "ən ucuz", en: "cheapest", ru: "дешевле всего" },
    "basket.noData": {
      az: "bu marketdə qiymət yoxdur",
      en: "no price in this store",
      ru: "в этом магазине нет цены",
    },
    "basket.noPriceAnywhere": {
      az: "heç bir marketdə qiyməti yoxdur",
      en: "no price in any store",
      ru: "нет цены ни в одном магазине",
    },
    "basket.missingN": {
      az: "{n} məhsul yoxdur",
      en: "{n} items missing",
      ru: "нет {n} товаров",
    },
    "basket.notCompared": {
      az: "müqayisədə iştirak etmir",
      en: "not part of the comparison",
      ru: "не участвует в сравнении",
    },
    "basket.someUnavailable": {
      az: "{n} məhsulun heç bir marketdə qiyməti yoxdur — cəm natamamdır.",
      en: "{n} items have no price in any store — the total is incomplete.",
      ru: "У {n} товаров нет цены ни в одном магазине — сумма неполная.",
    },
    "basket.noPlan": {
      az: "Plan qurmaq üçün kifayət qədər qiymət yoxdur.",
      en: "There are not enough prices to build a plan.",
      ru: "Недостаточно цен, чтобы построить план.",
    },
    "basket.emptyTotals": {
      az: "Səbət boşdur — müqayisə ediləcək bir şey yoxdur.",
      en: "The basket is empty — nothing to compare yet.",
      ru: "Корзина пуста — сравнивать нечего.",
    },
    "basket.emptyPlan": {
      az: "Məhsul əlavə edin, plan özü qurulacaq.",
      en: "Add an item and the plan builds itself.",
      ru: "Добавьте товар — план построится сам.",
    },
    "basket.goSearch": { az: "Məhsul axtar", en: "Search products", ru: "Найти товары" },
    "basket.loadError": {
      az: "Səbət yüklənmədi.",
      en: "Could not load the basket.",
      ru: "Не удалось загрузить корзину.",
    },
    "basket.more": { az: "Bir ədəd artır", en: "Increase by one", ru: "Добавить одну штуку" },
    "basket.less": { az: "Bir ədəd azalt", en: "Decrease by one", ru: "Убрать одну штуку" },

    "nav.panelSelect": { az: "Panel seçimi", en: "Panel selection", ru: "Выбор панели" },
    "nav.user": { az: "İstifadəçi", en: "User", ru: "Пользователь" },
    "admin.backToSite": { az: "Sayta qayıt", en: "Back to site", ru: "На сайт" },
    "nav.admin": { az: "Admin / Developer", en: "Admin / Developer", ru: "Админ / Разработчик" },
    "nav.profileJump": {
      az: "Profil və parametrlərə keç",
      en: "Go to profile and settings",
      ru: "Перейти к профилю и настройкам",
    },
    "nav.language": { az: "Dil seçimi", en: "Language", ru: "Язык" },

    "title.index": {
      az: "BasketIQ — supermarket qiymət kəşfiyyatı",
      en: "BasketIQ — supermarket price intelligence",
      ru: "BasketIQ — аналитика цен супермаркетов",
    },
    "title.product": { az: "Məhsul — BasketIQ", en: "Product — BasketIQ", ru: "Товар — BasketIQ" },
    "title.search": { az: "Axtarış — BasketIQ", en: "Search — BasketIQ", ru: "Поиск — BasketIQ" },

    // =============================================================== İLK EKRAN
    "hero.title": {
      az: "İstənilən məhsulun qiymətini müqayisə edin",
      en: "Compare the price of any product",
      ru: "Сравните цену любого товара",
    },
    "hero.sub": {
      az: "Dörd marketin qiymətini yan-yana göstəririk — harada ucuz olduğunu bir baxışda görün.",
      en: "We show four supermarkets' prices side by side — see where it is cheaper at a glance.",
      ru: "Показываем цены четырёх магазинов рядом — вы сразу увидите, где дешевле.",
    },
    "search.aria": { az: "Məhsul axtarışı", en: "Product search", ru: "Поиск товара" },
    "search.placeholder": {
      az: "Məhsul və ya brend axtarın — süd, Milla, yağ…",
      en: "Search for a product or brand — milk, Milla, oil…",
      ru: "Найдите товар или бренд — молоко, Milla, масло…",
    },
    "search.submit": { az: "Axtar", en: "Search", ru: "Найти" },

    // ================================================================ MARKETLƏR
    "stores.title": { az: "Marketlər", en: "Supermarkets", ru: "Магазины" },
    "stores.sub": {
      az: "Marketi seçin — həmin marketin endirimləri və məhsulları açılır.",
      en: "Pick a supermarket — its discounts and products open up.",
      ru: "Выберите магазин — откроются его скидки и товары.",
    },
    "stores.productCount": { az: "məhsul", en: "products", ru: "товаров" },

    // ================================================================ ENDİRİMLƏR
    "deals.title": {
      az: "Bugünün ən sərfəli endirimləri",
      en: "Today's best discounts",
      ru: "Лучшие скидки сегодня",
    },
    "deals.sub": {
      az: "Hər məhsul üçün ən böyük faiz endirim. Sağdakı sütunlar eyni məhsulun digər marketlərdəki qiymətidir — endirim həqiqi olsa da, qonşu market daha ucuz sata bilər.",
      en: "The biggest percentage discount for each product. The columns on the right show the same product's price at other supermarkets — even a real discount can be beaten by a neighbour.",
      ru: "Максимальная процентная скидка по каждому товару. Колонки справа — цена того же товара в других магазинах: даже настоящая скидка может оказаться дороже, чем у соседа.",
    },
    "deals.more": { az: "Daha çox göstər", en: "Show more", ru: "Показать ещё" },
    // SAYLA BİRLİKDƏ: «daha çox» nə qədərdir? Rəqəm olmadan düymə istifadəçidən
    // kor-koranə klik istəyir - siyahının 6, yoxsa 60 sətir uzanacağını bilmir.
    "deals.moreN": {
      az: "Daha {n} endirim göstər",
      en: "Show {n} more deals",
      ru: "Показать ещё {n}",
    },
    "deals.lessN": {
      az: "Yalnız ilk {n}-nı göstər",
      en: "Show only the first {n}",
      ru: "Показать только первые {n}",
    },
    "deals.available": { az: "Mövcuddur", en: "Available at", ru: "В наличии" },
    "deals.saving": { az: "qənaət", en: "saved", ru: "экономия" },
    "deals.onlyAt": { az: "Yalnız {store}-də tapılıb", en: "Found only at {store}", ru: "Найдено только в {store}" },

    // --- endirimin etibarı (A1) ---
    "trust.verified": { az: "Təsdiqlənmiş endirim", en: "Verified discount", ru: "Проверенная скидка" },
    "trust.unverified": { az: "Yoxlanılmayıb", en: "Unverified", ru: "Не проверено" },
    "trust.suspicious": { az: "Şübhəli endirim", en: "Suspicious discount", ru: "Подозрительная скидка" },
    "trust.verifiedHint": {
      az: "Köhnə qiymət öz müşahidələrimizlə təsdiqlənib",
      en: "The old price is confirmed by our own observations",
      ru: "Старая цена подтверждена нашими наблюдениями",
    },
    "trust.unverifiedHint": {
      az: "Bu məhsulun keçmiş qiymətini görməmişik - iddianı yoxlaya bilmirik",
      en: "We have not seen this product's past price — we cannot check the claim",
      ru: "Мы не видели прошлую цену этого товара — проверить заявление нельзя",
    },
    "trust.suspiciousHint": {
      az: "Endirim həddindən dərindir və ya köhnə qiymət şişirdilib",
      en: "The discount is implausibly deep or the old price is inflated",
      ru: "Скидка неправдоподобно глубокая или старая цена завышена",
    },

    // --- uyğunluq etibarı (A4) ---
    "match.exact": { az: "dəqiq uyğunluq", en: "exact match", ru: "точное совпадение" },
    "match.approximate": { az: "təxmini uyğunluq", en: "approximate match", ru: "приблизительное совпадение" },
    "match.exactHint": {
      az: "Marketlərdə eyni məhsul (eyni ad, brend və ölçü)",
      en: "The same product across supermarkets (same name, brand and size)",
      ru: "Один и тот же товар в магазинах (то же название, бренд и размер)",
    },
    "match.approximateHint": {
      az: "Məhsullar oxşarlığa görə birləşdirilib - eyni olmaya bilər",
      en: "The products were merged by similarity — they may not be identical",
      ru: "Товары объединены по схожести — они могут отличаться",
    },

    // --- əhatə (D18) ---
    "coverage.stores": {
      az: "{n} / {total} marketdə",
      en: "{n} of {total} supermarkets",
      ru: "{n} из {total} магазинов",
    },
    "coverage.noData": { az: "hələ data yoxdur", en: "no data yet", ru: "данных пока нет" },

    // ==================================================================== SƏBƏT
    "basket.title": { az: "Səbətiniz harada ucuzdur?", en: "Where is your basket cheaper?", ru: "Где ваша корзина дешевле?" },
    "basket.empty": { az: "Səbət boşdur", en: "Your basket is empty", ru: "Корзина пуста" },
    "basket.emptyHint": {
      az: "Aşağıdakı axtarışdan məhsul əlavə edin — cavab dərhal görünəcək.",
      en: "Add a product from the search below — the answer appears immediately.",
      ru: "Добавьте товар через поиск ниже — ответ появится сразу.",
    },
    "basket.storeDetail": { az: "Market üzrə ətraflı", en: "Details by supermarket", ru: "Подробно по магазинам" },
    "basket.label": { az: "Səbətiniz", en: "Your basket", ru: "Ваша корзина" },
    "basket.removeItem": {
      az: "{name} məhsulunu səbətdən sil",
      en: "Remove {name} from the basket",
      ru: "Убрать {name} из корзины",
    },

    // ================================================================ MÜQAYİSƏ
    "compare.title": { az: "Məhsul üzrə müqayisə", en: "Comparison by product", ru: "Сравнение по товарам" },
    // MƏTN QAYDANI DÜZGÜN DEYİR: nişan «hər sətirdə» deyil, yalnız MÜQAYİSƏ
    // olan sətirdə görünür. Bir market satırsa, «ən ucuz» heç nə demir -
    // əvvəlki mətn istifadəçiyə tapmayacağı nişanı vəd edirdi.
    "compare.sub": {
      az: "İki və daha çox marketdə satılan məhsulda ən ucuz qiymət ✓ nişanı ilə işarələnir.",
      en: "When two or more stores sell an item, its lowest price is marked with a ✓.",
      ru: "Если товар продают два и более магазина, самая низкая цена отмечается значком ✓.",
    },
    "compare.addLabel": { az: "Məhsul axtar və səbətə əlavə et", en: "Search a product and add it to the basket", ru: "Найдите товар и добавьте в корзину" },
    "compare.addPlaceholder": { az: "süd, düyü, yağ…", en: "milk, rice, oil…", ru: "молоко, рис, масло…" },
    "compare.caption": {
      az: "Səbətdəki məhsulların marketlər üzrə qiymət müqayisəsi",
      en: "Price comparison of the basket's products across supermarkets",
      ru: "Сравнение цен товаров корзины по магазинам",
    },
    "compare.cheapest": { az: "ən ucuz", en: "cheapest", ru: "самая низкая" },

    // ======================================================================= AI
    "ai.title": { az: "AI tövsiyəsi", en: "AI recommendation", ru: "Рекомендация ИИ" },
    "ai.get": { az: "Tövsiyə al", en: "Get a recommendation", ru: "Получить рекомендацию" },
    "ai.badge": { az: "AI", en: "AI", ru: "ИИ" },
    "ai.noteTitle": { az: "AI qeydi", en: "AI note", ru: "Заметка ИИ" },
    "ai.sub": {
      az: "Bütün rəqəmlər Python-da hesablanır — model yalnız onları izah edir.",
      en: "Every number is computed in Python — the model only explains them.",
      ru: "Все числа вычисляются в Python — модель лишь объясняет их.",
    },
    "ai.noteSub": {
      az: "Müştəri rəyi deyil — yuxarıdakı qiymətlərin bir cümləlik izahı.",
      en: "Not a customer review — a one-sentence explanation of the prices above.",
      ru: "Это не отзыв покупателя — одно предложение, объясняющее цены выше.",
    },
    "ai.facts": { az: "Faktlara bax", en: "See the facts", ru: "Посмотреть факты" },
    // Cümlə iki hissəyə bölünür, çünki ortasında düymənin adı qalın yazılır.
    // Üç dildə də düymənin adı SONDA qalır, ona görə «əvvəl/sonra» bölgüsü işləyir.
    "ai.placeholderBefore": {
      az: "Səbətinizi doldurun, sonra",
      en: "Fill your basket, then press",
      ru: "Наполните корзину, затем нажмите",
    },
    "ai.placeholderAfter": { az: " düyməsini basın.", en: ".", ru: "." },

    // ================================================================ TARİXÇƏ
    "history.title": { az: "Qiymət tarixçəsi", en: "Price history", ru: "История цен" },

    // ====================================================== ENDİRİM YOXLAMASI
    "discount.title": { az: "Endirim yoxlaması", en: "Discount check", ru: "Проверка скидки" },

    // ==================================================================== PROFİL
    "profile.title": { az: "Profil və parametrlər", en: "Profile and settings", ru: "Профиль и настройки" },
    "profile.household": { az: "Neçə nəfərlik ev", en: "Household size", ru: "Сколько человек в семье" },
    "profile.budget": { az: "Həftəlik büdcə (AZN)", en: "Weekly budget (AZN)", ru: "Недельный бюджет (AZN)" },
    "profile.storeCount": { az: "Neçə markete gedirsiniz", en: "How many supermarkets do you visit", ru: "Сколько магазинов вы посещаете" },
    "profile.storeCount1": { az: "1 — yalnız bir market", en: "1 — a single supermarket", ru: "1 — только один магазин" },
    "profile.storeCount2": { az: "2 — bölə bilərəm", en: "2 — I can split the trip", ru: "2 — могу разделить" },
    "profile.minSaving": { az: "2-ci market üçün min. qənaət", en: "Min. saving for a 2nd supermarket", ru: "Мин. экономия для 2-го магазина" },
    "profile.avoid": { az: "İstəmədiyiniz sözlər (vergüllə)", en: "Words to avoid (comma separated)", ru: "Нежелательные слова (через запятую)" },
    "profile.avoidPlaceholder": { az: "məsələn: donuz, alkoqol", en: "e.g. pork, alcohol", ru: "например: свинина, алкоголь" },
    "profile.unitPrice": { az: "kq/litr qiymətinə bax", en: "Compare by kg/litre price", ru: "Смотреть цену за кг/литр" },
    "profile.save": { az: "Planı yenilə", en: "Update the plan", ru: "Обновить план" },
    "profile.planTitle": { az: "Sizə tövsiyə olunan plan", en: "Your recommended plan", ru: "Рекомендованный вам план" },

    // ===================================================================== ADMİN
    "admin.title": { az: "Admin / Developer", en: "Admin / Developer", ru: "Админ / Разработчик" },
    "admin.sub": {
      az: "Data mənbələri, kataloq emalı və sistem diaqnostikası.",
      en: "Data sources, catalogue processing and system diagnostics.",
      ru: "Источники данных, обработка каталогов и диагностика системы.",
    },
    "admin.hint": {
      az: "Yuxarıdakı istifadəçi paneli buradakı kataloqlardan qidalanır: mənbədən çək və ya əl ilə yüklə, sonra AI ilə emal et.",
      en: "The user panel above is fed by the catalogues here: fetch from a source or upload manually, then process with AI.",
      ru: "Пользовательская панель выше питается этими каталогами: загрузите из источника или вручную, затем обработайте ИИ.",
    },
    // ------------------------------------------------- KARANTİN NÖVBƏSİ (C12)
    // Bayraq adları bazada İNGİLİS açarları kimi saxlanılır
    // (`ingestion/quality.py`); ekranda görünən mətn yalnız burada yaşayır.
    "flag.deepDiscount": {
      az: "Dərin endirim",
      en: "Deep discount",
      ru: "Глубокая скидка",
    },
    "flag.priceOutlier": {
      az: "Qiymət tarixçədən kənar",
      en: "Price outlier",
      ru: "Цена вне истории",
    },
    "flag.unitOutlier": {
      az: "Vahid qiyməti normadan kənar",
      en: "Unit price outlier",
      ru: "Цена за единицу вне нормы",
    },

    "review.title": {
      az: "Karantin növbəsi",
      en: "Quarantine queue",
      ru: "Очередь на проверку",
    },
    "review.sub": {
      az: "Sağlamlıq yoxlamasından keçməyən qiymətlər. Bu sətirlər istifadəçiyə göstərilmir; baxıb təsdiqləsən, yenidən ekrana qayıdır.",
      en: "Prices that failed the sanity check. They are hidden from users; approve one and it returns to the site.",
      ru: "Цены, не прошедшие проверку. Пользователям они не показываются; после подтверждения возвращаются на сайт.",
    },
    "review.empty": {
      az: "Baxış gözləyən sətir yoxdur.",
      en: "Nothing is waiting for review.",
      ru: "Нет строк, ожидающих проверки.",
    },
    "review.total": {
      az: "{n} sətir baxış gözləyir",
      en: "{n} rows awaiting review",
      ru: "{n} строк ожидают проверки",
    },
    "review.approve": { az: "Təsdiqlə", en: "Approve", ru: "Подтвердить" },
    "review.approved": { az: "Təsdiqləndi", en: "Approved", ru: "Подтверждено" },
    "review.loadError": {
      az: "Növbə yüklənmədi.",
      en: "Could not load the queue.",
      ru: "Не удалось загрузить очередь.",
    },
    "review.was": { az: "əvvəl", en: "was", ru: "было" },

    // ------------------------------------------------ NATAMAM ƏHATƏ (D16/D17)
    "compare.noData": { az: "tezliklə", en: "coming soon", ru: "скоро" },
    "bars.noData": {
      az: "kataloq hələ gəlməyib",
      en: "catalogue not loaded yet",
      ru: "каталог ещё не загружен",
    },
    "bars.notSelling": {
      az: "səbətdəki məhsulları satmır",
      en: "does not sell the basket items",
      ru: "не продаёт товары из корзины",
    },
    "bars.notCompared": {
      az: "Müqayisədə iştirak etmir",
      en: "Not part of the comparison",
      ru: "Не участвует в сравнении",
    },

    // ------------------------------------------------------------- REKLAM (E19-E24)
    // «Reklam» sözü ÜÇ DİLDƏ də açıq yazılır: sponsorlu məzmunun
    // nişanlanması qaydadır, tərcümə seçimi deyil.
    "ads.sponsored": { az: "Reklam", en: "Sponsored", ru: "Реклама" },
    // Yan lövhənin `aria-label`-ı: ekran oxuyucusu bölmənin reklam olduğunu
    // BAŞLANĞICDA bilməlidir - kreativi dinlədikdən sonra yox.
    "ads.label": { az: "Reklam", en: "Advertisement", ru: "Реклама" },
    "ads.slotLabel": { az: "Reklam yeri", en: "Ad space", ru: "Рекламное место" },
    "ads.emptyTitle": {
      az: "Sizin reklamınız burada ola bilər",
      en: "Your ad could be here",
      ru: "Здесь может быть ваша реклама",
    },
    "ads.emptyBody": {
      az: "Ana səhifənin bu yeri boşdur — qiymət axtaran istifadəçilərə görünün.",
      en: "This spot on the home page is free — get in front of people comparing prices.",
      ru: "Это место на главной свободно — покажитесь тем, кто сравнивает цены.",
    },
    "ads.cta": { az: "Reklam ver", en: "Advertise here", ru: "Разместить рекламу" },
    "ads.mailSubject": {
      az: "BasketIQ-də reklam",
      en: "Advertising on BasketIQ",
      ru: "Реклама на BasketIQ",
    },

    // -------------------------------------------------- REKLAM MENECERİ (E22)
    "adsAdmin.title": { az: "Reklam sifarişləri", en: "Ad orders", ru: "Рекламные заказы" },
    "adsAdmin.sub": {
      az: "Yalnız AKTİV və tarix aralığında olan sifariş göstərilir — müddəti bitən reklam öz-özünə dayanır.",
      en: "Only orders that are active and within their dates are shown — an expired ad stops on its own.",
      ru: "Показываются только активные заказы в пределах срока — истёкшая реклама останавливается сама.",
    },
    "adsAdmin.ad": { az: "Sifariş", en: "Order", ru: "Заказ" },
    "adsAdmin.slot": { az: "Yer", en: "Slot", ru: "Место" },
    "adsAdmin.impressions": { az: "Göstərim", en: "Impressions", ru: "Показы" },
    "adsAdmin.clicks": { az: "Klik", en: "Clicks", ru: "Клики" },
    "adsAdmin.advertiser": { az: "Reklamverən", en: "Advertiser", ru: "Рекламодатель" },
    "adsAdmin.adTitle": { az: "Başlıq", en: "Title", ru: "Заголовок" },
    "adsAdmin.body": { az: "Qısa mətn", en: "Short text", ru: "Короткий текст" },
    "adsAdmin.url": { az: "Hədəf ünvan", en: "Target URL", ru: "Целевая ссылка" },
    "adsAdmin.start": { az: "Başlanğıc", en: "Start", ru: "Начало" },
    "adsAdmin.end": { az: "Bitmə", en: "End", ru: "Конец" },
    "adsAdmin.creative": {
      az: "Kreativ (PNG/JPG/WEBP, max 2 MB)",
      en: "Creative (PNG/JPG/WEBP, max 2 MB)",
      ru: "Креатив (PNG/JPG/WEBP, макс. 2 МБ)",
    },
    "adsAdmin.active": { az: "Aktiv", en: "Active", ru: "Активен" },
    "adsAdmin.create": { az: "Sifarişi yarat", en: "Create order", ru: "Создать заказ" },
    "adsAdmin.saved": { az: "Sifariş yaradıldı.", en: "Order created.", ru: "Заказ создан." },
    "adsAdmin.saveError": {
      az: "Sifariş yazılmadı.",
      en: "The order was not saved.",
      ru: "Заказ не сохранён.",
    },
    "adsAdmin.loadError": {
      az: "Sifarişlər yüklənmədi.",
      en: "Could not load the orders.",
      ru: "Не удалось загрузить заказы.",
    },
    "adsAdmin.empty": {
      az: "Hələ sifariş yoxdur — slot «bu yer satılır» vəziyyətindədir.",
      en: "No orders yet — the slot shows its “this space is for sale” state.",
      ru: "Заказов пока нет — слот показывает «это место продаётся».",
    },
    "adsAdmin.live": { az: "efirdə", en: "live", ru: "в эфире" },
    "adsAdmin.paused": { az: "dayanıb", en: "paused", ru: "остановлен" },
    "adsAdmin.sample": { az: "nümunə", en: "sample", ru: "пример" },
    "adsAdmin.offPage": { az: "səhifədə görünmür", en: "not on any page", ru: "нет на странице" },
    "adsAdmin.pause": { az: "Dayandır", en: "Pause", ru: "Остановить" },
    "adsAdmin.resume": { az: "Davam et", en: "Resume", ru: "Возобновить" },

    // ----------------------------------------------------- MARKET ƏHATƏSİ (D15)
    "coverage.title": { az: "Market əhatəsi", en: "Store coverage", ru: "Охват магазинов" },
    "coverage.sub": {
      az: "Datası olan market ana səhifədə avtomatik işlək olur — ayrıca aktivləşdirmə addımı yoxdur. Kataloq yüklə və ya mənbədən çək.",
      en: "A store goes live automatically once it has data — there is no separate activation step. Upload a catalogue or fetch the source.",
      ru: "Магазин включается автоматически, как только появляются данные — отдельного шага активации нет. Загрузите каталог или заберите источник.",
    },
    "coverage.market": { az: "Market", en: "Store", ru: "Магазин" },
    "coverage.share": { az: "Əhatə", en: "Coverage", ru: "Охват" },
    "coverage.updated": { az: "Son yenilənmə", en: "Last updated", ru: "Обновлено" },
    "coverage.source": { az: "Mənbə", en: "Source", ru: "Источник" },
    "coverage.never": { az: "heç vaxt", en: "never", ru: "никогда" },
    "coverage.live": { az: "işlək", en: "live", ru: "активен" },
    "coverage.loadError": {
      az: "Əhatə cədvəli yüklənmədi.",
      en: "Could not load the coverage table.",
      ru: "Не удалось загрузить таблицу охвата.",
    },

    // ------------------------------------------------------ MƏNBƏ VƏZİYYƏTİ (D14)
    "source.active": { az: "işlək", en: "live", ru: "активен" },
    "source.manual": { az: "əl ilə", en: "manual", ru: "вручную" },
    "source.blocked": { az: "bağlı", en: "blocked", ru: "недоступен" },

    "admin.statusTitle": { az: "Sistem statusu", en: "System status", ru: "Состояние системы" },
    "admin.scrapeTitle": { az: "Mənbədən avtomatik çək", en: "Fetch automatically from a source", ru: "Автоматическая загрузка из источника" },
    "admin.scrapeSub": {
      az: "Market saytından endirim jurnalını tapıb endirir və emal edir.",
      en: "Finds the discount leaflet on the supermarket's site, downloads and processes it.",
      ru: "Находит журнал скидок на сайте магазина, скачивает и обрабатывает его.",
    },
    "admin.scrapeRobots": {
      az: "-ə riayət olunur, sorğular arasında gecikmə qoyulur.",
      en: "is respected, and requests are spaced out with a delay.",
      ru: "соблюдается, между запросами делается пауза.",
    },
    "admin.pagesLabel": { az: "Neçə səhifə emal olunsun?", en: "How many pages to process?", ru: "Сколько страниц обработать?" },
    "admin.page1": { az: "1 səhifə", en: "1 page", ru: "1 страница" },
    "admin.page2": { az: "2 səhifə", en: "2 pages", ru: "2 страницы" },
    "admin.page3": { az: "3 səhifə", en: "3 pages", ru: "3 страницы" },
    "admin.page5": { az: "5 səhifə", en: "5 pages", ru: "5 страниц" },
    "admin.scrapeBtn": { az: "Mənbədən çək", en: "Fetch from source", ru: "Загрузить из источника" },
    "admin.uploadTitle": { az: "Kataloq yüklə", en: "Upload a catalogue", ru: "Загрузить каталог" },
    "admin.dropzoneAria": {
      az: "Kataloq faylı seç — PDF, JPG və ya PNG",
      en: "Choose a catalogue file — PDF, JPG or PNG",
      ru: "Выберите файл каталога — PDF, JPG или PNG",
    },
    "admin.dropHere": { az: "Faylı bura sürüşdürün", en: "Drag the file here", ru: "Перетащите файл сюда" },
    "admin.or": { az: "və ya", en: "or", ru: "или" },
    "admin.clickToPick": { az: "seçmək üçün klikləyin", en: "click to choose", ru: "нажмите, чтобы выбрать" },
    "admin.storeName": { az: "Market adı", en: "Supermarket name", ru: "Название магазина" },
    "admin.storePlaceholder": { az: "Məsələn: Bravo", en: "For example: Bravo", ru: "Например: Bravo" },
    "admin.psmLabel": { az: "PSM (OCR rejimi)", en: "PSM (OCR mode)", ru: "PSM (режим OCR)" },
    "admin.psmAuto": { az: "avtomatik (.env)", en: "automatic (.env)", ru: "автоматически (.env)" },
    "admin.psm6": { az: "6 — vahid blok", en: "6 — single block", ru: "6 — единый блок" },
    "admin.psm4": { az: "4 — sütunlu mətn", en: "4 — columnar text", ru: "4 — текст в колонках" },
    "admin.psm11": { az: "11 — səpələnmiş mətn", en: "11 — sparse text", ru: "11 — разрозненный текст" },
    "admin.psm3": { az: "3 — tam avtomatik", en: "3 — fully automatic", ru: "3 — полностью автоматически" },
    "admin.forceOcr": { az: "OCR-ı məcbur et", en: "Force OCR", ru: "Принудительный OCR" },
    "admin.process": { az: "Emal et", en: "Process", ru: "Обработать" },
    "admin.noFile": { az: "Fayl seçilməyib", en: "No file selected", ru: "Файл не выбран" },
    "admin.resultTitle": {
      az: "Emal nəticəsi — təmizlənmiş sətirlər",
      en: "Processing result — cleaned lines",
      ru: "Результат обработки — очищенные строки",
    },
    "admin.linesLabel": { az: "Neçə sətir emal olunsun?", en: "How many lines to process?", ru: "Сколько строк обработать?" },
    "admin.lines5": { az: "5 sətir", en: "5 lines", ru: "5 строк" },
    "admin.lines10": { az: "10 sətir", en: "10 lines", ru: "10 строк" },
    "admin.lines25": { az: "25 sətir", en: "25 lines", ru: "25 строк" },
    "admin.extract": { az: "AI ilə çıxar", en: "Extract with AI", ru: "Извлечь с ИИ" },
    "admin.match": { az: "Məhsulları uyğunlaşdır", en: "Match products", ru: "Сопоставить товары" },
    "admin.extractedTitle": { az: "AI-nin çıxardığı məhsullar", en: "Products extracted by AI", ru: "Товары, извлечённые ИИ" },
    "admin.catalogsTitle": { az: "Yüklənmiş kataloqlar", en: "Uploaded catalogues", ru: "Загруженные каталоги" },
    "admin.lines": { az: "Sətirlər", en: "Lines", ru: "Строки" },
    "admin.deleteCatalog": {
      az: "{store} kataloqunu sil",
      en: "Delete the {store} catalogue",
      ru: "Удалить каталог {store}",
    },

    "deals.less": { az: "Daha az göstər", en: "Show less", ru: "Показать меньше" },
    "deals.empty": {
      az: "Hazırda endirimli məhsul tapılmadı. Admin panelindən kataloq yükləyin.",
      en: "No discounted product right now. Upload a catalogue from the admin panel.",
      ru: "Сейчас нет товаров со скидкой. Загрузите каталог в панели администратора.",
    },
    "deals.loadError": {
      az: "Endirim siyahısı yüklənmədi. Səhifənin qalan hissəsi işləyir.",
      en: "The discount list did not load. The rest of the page still works.",
      ru: "Список скидок не загрузился. Остальная часть страницы работает.",
    },

    "stores.empty": { az: "Market siyahısı boşdur.", en: "The supermarket list is empty.", ru: "Список магазинов пуст." },
    "stores.loadError": {
      az: "Market siyahısı yüklənmədi. Səhifənin qalan hissəsi işləyir.",
      en: "The supermarket list did not load. The rest of the page still works.",
      ru: "Список магазинов не загрузился. Остальная часть страницы работает.",
    },

    "search.clear": { az: "Təmizlə", en: "Clear", ru: "Очистить" },
    "search.allProducts": { az: "Bütün məhsullar", en: "All products", ru: "Все товары" },
    "search.storeCount": { az: "{n} marketdə", en: "at {n} supermarkets", ru: "в {n} магазинах" },
    "search.loadError": { az: "Nəticələr yüklənmədi.", en: "Results did not load.", ru: "Результаты не загрузились." },

    "store.noSource": {
      az: "Bu marketin data mənbəyi hələ hazır deyil.",
      en: "The data source for this supermarket is not ready yet.",
      ru: "Источник данных этого магазина пока не готов.",
    },
    "store.soonTitle": { az: "Tezliklə.", en: "Coming soon.", ru: "Скоро." },
    "store.soonBody": {
      az: "{store} üçün qiymət mənbəyi hələ qoşulmayıb, ona görə burada göstərəcək qiymətimiz yoxdur. Qoşulan kimi məhsullar bu səhifədə görünəcək — o vaxta qədər müqayisə digər marketlərlə aparılır.",
      en: "The price source for {store} is not connected yet, so we have no prices to show here. Products will appear on this page as soon as it is connected — until then the comparison runs with the other supermarkets.",
      ru: "Источник цен для {store} ещё не подключён, поэтому показывать здесь нечего. Товары появятся на этой странице сразу после подключения — до тех пор сравнение идёт по другим магазинам.",
    },
    "store.notFound": { az: "Market tapılmadı", en: "Supermarket not found", ru: "Магазин не найден" },
    "store.notFoundBody": {
      az: "Bu ünvanda market yoxdur.",
      en: "There is no supermarket at this address.",
      ru: "По этому адресу магазина нет.",
    },
    "store.backHome": { az: "Ana səhifəyə qayıt", en: "Back to the home page", ru: "Вернуться на главную" },
    "store.loadError": { az: "Market datası yüklənmədi.", en: "Supermarket data did not load.", ru: "Данные магазина не загрузились." },

    // -------------------------------------------------- səbət cavabı (app.js)
    "answer.cheaperThan": {
      az: "{store} ilə müqayisədə {amount} ucuz",
      en: "{amount} cheaper than {store}",
      ru: "На {amount} дешевле, чем {store}",
    },
    "answer.cheapestCount": {
      az: "Ən ucuz qiymət: {n} / {total} məhsulda",
      en: "Lowest price on {n} of {total} products",
      ru: "Самая низкая цена по {n} из {total} товаров",
    },
    "answer.noneComplete": {
      az: "Heç bir market səbətin hamısını satmır.",
      en: "No supermarket sells the whole basket.",
      ru: "Ни один магазин не продаёт всю корзину.",
    },
    "answer.unavailable": {
      az: " {n} məhsul heç bir marketdə tapılmadı.",
      en: " {n} products were not found at any supermarket.",
      ru: " {n} товаров не найдено ни в одном магазине.",
    },
    "answer.noWinner": { az: "Qalib elan edilmir", en: "No winner is declared", ru: "Победитель не объявляется" },
    "answer.split": {
      az: "{n} marketi gəzsəniz daha {amount} qənaət edərsiniz",
      en: "Visit {n} supermarkets and you save {amount} more",
      ru: "Обойдите {n} магазина — сэкономите ещё {amount}",
    },
    "answer.fullBasket": { az: "ən ucuz tam səbət", en: "cheapest complete basket", ru: "самая дешёвая полная корзина" },

    // Böyük rəqəmin NƏ OLDUĞU. Əvvəl yalnız «6.14 ₼» yazılırdı və rəqəmin
    // bütün məhsulların cəmi olduğu heç yerdə deyilmirdi.
    "answer.allItems": {
      az: "Hər {n} məhsul bir yerdə",
      en: "All {n} products together",
      ru: "Все {n} товара вместе",
    },
    "answer.cheapestFull": {
      az: "Ən ucuz tam səbət — {store}",
      en: "Cheapest complete basket — {store}",
      ru: "Самая дешёвая полная корзина — {store}",
    },
    "answer.onlyOneComplete": {
      az: "Tam səbəti yalnız 1 market satır",
      en: "Only 1 supermarket sells the complete basket",
      ru: "Полную корзину продаёт только 1 магазин",
    },

    // Bölünmüş alışın HESABI. «0.16 ₼ qənaət» rəqəminin haradan gəldiyi
    // izah olunmurdu - istifadəçinin ona inanmaq üçün əsası yox idi.
    "answer.splitHead": {
      az: "{n} marketə getsəniz {amount} qənaət",
      en: "Visit {n} supermarkets and save {amount}",
      ru: "Обойдите {n} магазина — сэкономите {amount}",
    },
    "answer.splitItem": {
      az: "{label} — {store} ({price})",
      en: "{label} — {store} ({price})",
      ru: "{label} — {store} ({price})",
    },
    "answer.splitSum": {
      az: "Cəmi {sum} — {store} marketindən hər şeyi almaqdan {amount} ucuz",
      en: "Total {sum} — {amount} cheaper than buying everything at {store}",
      ru: "Итого {sum} — на {amount} дешевле, чем всё в {store}",
    },

    // Natamam səbətlər müqayisə oxundan KƏNARDIR.
    "bars.completeHead": {
      az: "Tam səbət — müqayisə",
      en: "Complete basket — comparison",
      ru: "Полная корзина — сравнение",
    },
    "bars.partialHead": {
      az: "Natamam səbət — müqayisəyə girmir",
      en: "Incomplete basket — not compared",
      ru: "Неполная корзина — не сравнивается",
    },
    "bars.partialWhy": {
      az: "Yalnız {covered}/{total} məhsul var — cəmi qalanları saymır",
      en: "Only {covered}/{total} products — the total excludes the rest",
      ru: "Только {covered}/{total} товаров — сумма не включает остальные",
    },
    "bars.noComplete": {
      az: "Heç bir market səbətin hamısını satmır — müqayisə oxu qurulmur.",
      en: "No supermarket sells the whole basket — no comparison axis.",
      ru: "Ни один магазин не продаёт всю корзину — шкала не строится.",
    },
    "answer.partial": {
      az: "{covered}/{total} məhsul — natamam",
      en: "{covered}/{total} products — incomplete",
      ru: "{covered}/{total} товаров — неполно",
    },
    "answer.readyForAi": {
      az: "Səbətiniz hazırdır —",
      en: "Your basket is ready —",
      ru: "Ваша корзина готова —",
    },
    "answer.readyForAiAfter": {
      az: " düyməsi ilə izah alın.",
      en: " for an explanation.",
      ru: " за объяснением.",
    },
    "compare.emptyBasket": { az: "Səbətdə məhsul yoxdur.", en: "There are no products in the basket.", ru: "В корзине нет товаров." },
    "compare.loadError": {
      az: "Müqayisə yüklənmədi — backend cavab vermir.",
      en: "The comparison did not load — the backend is not responding.",
      ru: "Сравнение не загрузилось — бэкенд не отвечает.",
    },
    "compare.srCheapest": { az: "— ən ucuz", en: "— cheapest", ru: "— самая низкая" },

    // ------------------------------------------------ məhsul axtarışı (app.js)
    "add.notFound": { az: "Tapılmadı", en: "Not found", ru: "Не найдено" },
    "add.aria": {
      az: "{name} məhsulunu səbətə əlavə et",
      en: "Add {name} to the basket",
      ru: "Добавить {name} в корзину",
    },
    "add.done": { az: "Əlavə olundu", en: "Added", ru: "Добавлено" },
    "confirm.aria": {
      az: "{label} — təsdiq üçün yenidən basın",
      en: "{label} — press again to confirm",
      ru: "{label} — нажмите ещё раз для подтверждения",
    },

    // ------------------------------------------------------ admin emalı (app.js)
    "admin.unknownStore": { az: "Naməlum market", en: "Unknown supermarket", ru: "Неизвестный магазин" },
    "admin.processing": {
      az: "Emal olunur… Skan PDF-də OCR bir neçə dəqiqə çəkə bilər.",
      en: "Processing… OCR on a scanned PDF can take a few minutes.",
      ru: "Обработка… OCR отсканированного PDF может занять несколько минут.",
    },
    "admin.unknownError": { az: "Naməlum xəta", en: "Unknown error", ru: "Неизвестная ошибка" },
    "admin.ready": {
      az: "Hazırdır — {n} məhsul namizədi sətir tapıldı.",
      en: "Done — {n} candidate product lines found.",
      ru: "Готово — найдено строк-кандидатов: {n}.",
    },
    "admin.networkError": { az: "Şəbəkə xətası: ", en: "Network error: ", ru: "Сетевая ошибка: " },
    "admin.imageOcr": { az: "Şəkil — OCR", en: "Image — OCR", ru: "Изображение — OCR" },
    "admin.noLines": {
      az: "Heç bir məhsul sətri tapılmadı. PSM rejimini dəyişib yenidən yoxlayın.",
      en: "No product line was found. Change the PSM mode and try again.",
      ru: "Строк с товарами не найдено. Измените режим PSM и попробуйте снова.",
    },
    "admin.error": { az: "Xəta", en: "Error", ru: "Ошибка" },
    "admin.errorPrefix": { az: "Xəta: ", en: "Error: ", ru: "Ошибка: " },
    "admin.skipped": { az: "ötürüldü", en: "skipped", ru: "пропущено" },
    "admin.noExtract": { az: "Məhsul çıxarılmadı.", en: "No product was extracted.", ru: "Ни один товар не извлечён." },
    "admin.noCatalog": { az: "Hələ kataloq yüklənməyib.", en: "No catalogue has been uploaded yet.", ru: "Каталоги ещё не загружены." },
    "admin.listError": { az: "Siyahı yüklənmədi", en: "The list did not load", ru: "Список не загрузился" },
    // ====================================================== UYĞUNLUQ YOXLAMASI (ADDIM 5)
    "matches.title": { az: "Uyğunluq yoxlaması", en: "Match review", ru: "Проверка совпадений" },
    "matches.sub": {
      az: "Maşının əmin olmadığı cütlər. Qərarınız dərhal səbət müqayisəsinə düşür və növbəti avtomatik qaçış onu dəyişmir.",
      en: "Pairs the system is not sure about. Your decision reaches the basket comparison immediately and later automatic runs never override it.",
      ru: "Пары, в которых система не уверена. Ваше решение сразу попадает в сравнение корзины, и автоматические запуски его не меняют.",
    },
    "matches.back": { az: "Adminə qayıt", en: "Back to admin", ru: "Назад в админку" },
    "matches.queue": { az: "Növbə", en: "Queue", ru: "Очередь" },
    "matches.tabPending": { az: "Gözləyir", en: "Pending", ru: "Ожидают" },
    "matches.tabLlm": { az: "LLM qərarı", en: "LLM decision", ru: "Решение LLM" },
    "matches.same": { az: "Bəli, eynidir", en: "Yes, same", ru: "Да, одинаковые" },
    "matches.different": { az: "Xeyr, ayrıdır", en: "No, different", ru: "Нет, разные" },
    "matches.reasonSize": { az: "Ölçü bilinmir", en: "Size unknown", ru: "Размер неизвестен" },
    "matches.llmSame": { az: "LLM: eynidir", en: "LLM: same", ru: "LLM: одинаковые" },
    "matches.llmDifferent": { az: "LLM: fərqlidir", en: "LLM: different", ru: "LLM: разные" },
    "matches.similarity": { az: "Oxşarlıq", en: "Similarity", ru: "Сходство" },
    "matches.shelf": { az: "rəf", en: "shelf", ru: "полка" },
    "matches.catalog": { az: "kataloq", en: "catalog", ru: "каталог" },
    "matches.noPrice": { az: "Qiymət yoxdur", en: "No price", ru: "Нет цены" },
    "matches.empty": {
      az: "Növbə boşdur — hamısına baxılıb.",
      en: "The queue is empty — everything has been reviewed.",
      ru: "Очередь пуста — всё проверено.",
    },
    "matches.refused": {
      az: "Qərar yazıldı, amma birləşmədi: bir qrupda eyni marketin iki məhsulu və ya iki fərqli ölçü olardı.",
      en: "Decision saved, but not merged: the group would contain two products from one store or two different sizes.",
      ru: "Решение сохранено, но не объединено: в группе оказались бы два товара одного магазина или два разных размера.",
    },
    "matches.error": { az: "Xəta baş verdi", en: "Something went wrong", ru: "Произошла ошибка" },
    "matches.saved": { az: "Qərar yadda saxlanıldı", en: "Decision saved", ru: "Решение сохранено" },
    "matches.open": { az: "Yoxlamaya keç", en: "Open review", ru: "Перейти к проверке" },
    "matches.linkSub": {
      az: "Maşının əmin olmadığı məhsul cütləri — bir kliklə «eynidir» və ya «ayrıdır».",
      en: "Product pairs the system is not sure about — one click: “same” or “different”.",
      ru: "Пары товаров, в которых система не уверена, — одним кликом «одинаковые» или «разные».",
    },
    "admin.matching": {
      az: "Oxşar məhsullar axtarılır, sonra model onları yoxlayır…",
      en: "Looking for similar products, then the model verifies them…",
      ru: "Ищем похожие товары, затем модель их проверяет…",
    },

    "badge.pages": { az: "səhifə", en: "pages", ru: "страниц" },
    "badge.rawLines": { az: "xam sətir", en: "raw lines", ru: "сырых строк" },
    "badge.kept": { az: "saxlanıldı", en: "kept", ru: "сохранено" },
    "badge.ratio": { az: "nisbət", en: "ratio", ru: "доля" },
    "col.old": { az: "Köhnə", en: "Old", ru: "Старая" },
    "col.line": { az: "Sətir", en: "Line", ru: "Строка" },
    "col.brand": { az: "Brend", en: "Brand", ru: "Бренд" },
    "col.size": { az: "Ölçü", en: "Size", ru: "Размер" },
    "col.action": { az: "Əməliyyat", en: "Action", ru: "Действие" },
    "admin.modelWorking": {
      az: "Model sətirləri emal edir…",
      en: "The model is processing the lines…",
      ru: "Модель обрабатывает строки…",
    },
    "admin.cacheHint": {
      az: "Keşdə olan sətirlər dərhal qayıdır.",
      en: "Cached lines come back immediately.",
      ru: "Строки из кеша возвращаются сразу.",
    },
    "admin.savedCount": { az: "məhsul yazıldı", en: "products written", ru: "товаров записано" },
    "admin.fromCache": { az: "keşdən", en: "from cache", ru: "из кеша" },
    "admin.fromModel": { az: "modeldən", en: "from the model", ru: "от модели" },

    // ------------------------------------------------ admin sayğacları (app.js)
    "stat.stores": { az: "Market", en: "Supermarkets", ru: "Магазины" },
    "stat.storesNote": { az: "Qiyməti olan supermarket", en: "Supermarkets with prices", ru: "Магазины с ценами" },
    "stat.catalogs": { az: "Kataloq", en: "Catalogues", ru: "Каталоги" },
    "stat.catalogsNote": { az: "Emal olunmuş fayl", en: "Processed files", ru: "Обработанные файлы" },
    "stat.productsNote": { az: "AI ilə çıxarılmış sətir", en: "Lines extracted with AI", ru: "Строки, извлечённые ИИ" },
    "stat.pricesNote": { az: "Ümumi müşahidə", en: "Total observations", ru: "Всего наблюдений" },

    // ------------------------------------------------------ sistem statusu (app.js)
    "health.ok": { az: "işləyir", en: "working", ru: "работает" },
    "health.fail": { az: "xəta", en: "error", ru: "ошибка" },
    "health.checking": { az: "yoxlanılır", en: "checking", ru: "проверяется" },
    "health.llmProvider": { az: "LLM provayderi", en: "LLM provider", ru: "Провайдер LLM" },
    "health.activeModel": { az: "Aktiv model", en: "Active model", ru: "Активная модель" },
    "health.ollama": { az: "Ollama serveri", en: "Ollama server", ru: "Сервер Ollama" },
    "health.fallback": { az: "Ehtiyat: ", en: "Fallback: ", ru: "Резерв: " },
    "health.noResponse": { az: "Cavab vermir", en: "Not responding", ru: "Не отвечает" },
    "health.database": { az: "Verilənlər bazası", en: "Database", ru: "База данных" },
    "health.connected": { az: "Qoşuludur", en: "Connected", ru: "Подключена" },
    "health.reachable": { az: "Əlçatandır", en: "Reachable", ru: "Доступен" },
    "health.unreachable": { az: "Əlçatmazdır", en: "Unreachable", ru: "Недоступен" },
    "health.environment": { az: "Mühit", en: "Environment", ru: "Окружение" },
    "health.uvicorn": { az: "uvicorn işləyirmi?", en: "is uvicorn running?", ru: "запущен ли uvicorn?" },

    // ------------------------------------------------- tarixçə / qrafik
    "chart.noPrices": {
      az: "Hələ qiymət yoxdur — əvvəlcə kataloq emal edin.",
      en: "No prices yet — process a catalogue first.",
      ru: "Цен пока нет — сначала обработайте каталог.",
    },
    "chart.observations": { az: "müşahidə", en: "observations", ru: "наблюдений" },
    "chart.markets": { az: "market", en: "supermarkets", ru: "магазинов" },
    "chart.listError": { az: "Məhsul siyahısı yüklənmədi.", en: "The product list did not load.", ru: "Список товаров не загрузился." },
    "chart.historyError": { az: "Tarixçə yüklənmədi.", en: "The history did not load.", ru: "История не загрузилась." },
    "chart.noObservation": { az: "Bu məhsul üçün müşahidə yoxdur.", en: "There is no observation for this product.", ru: "По этому товару нет наблюдений." },
    "chart.noTrend": {
      az: "Eyni marketdən 2 müşahidə olmadığı üçün trend yox,",
      en: "Without two observations from the same supermarket there is no trend, so a",
      ru: "Без двух наблюдений из одного магазина тренда нет, поэтому показано",
    },
    "chart.storeCompare": { az: "market müqayisəsi", en: "supermarket comparison", ru: "сравнение магазинов" },
    "chart.shown": { az: "göstərilir.", en: "is shown.", ru: "показано." },
    "chart.lowestSeen": { az: " — ən ucuz", en: " — cheapest", ru: " — самая низкая" },
    "discount.loadError": { az: "Endirim yoxlaması yüklənmədi.", en: "The discount check did not load.", ru: "Проверка скидки не загрузилась." },

    "chart.market": { az: "Market", en: "Supermarket", ru: "Магазин" },
    "chart.oldPrice": { az: "Köhnə", en: "Old", ru: "Старая" },
    "chart.unitPrice": { az: "Vahid qiymət", en: "Unit price", ru: "Цена за единицу" },
    "chart.date": { az: "Tarix", en: "Date", ru: "Дата" },
    "chart.lowestSeenAt": { az: "ən aşağı müşahidə — {store}", en: "lowest observed — {store}", ru: "минимум зафиксирован — {store}" },
    "history.sub": {
      az: "Eyni marketdən 2 müşahidə olmayanda trend yox, market müqayisəsi göstərilir.",
      en: "Without two observations from the same supermarket a comparison across supermarkets is shown instead of a trend.",
      ru: "Если из одного магазина нет двух наблюдений, вместо тренда показывается сравнение магазинов.",
    },
    "discount.sub": {
      az: "Kataloqdakı «köhnə qiymət» iddiasını öz müşahidələrimizlə tutuşdururuq.",
      en: "We check the leaflet's \u00ableaflet old price\u00bb claim against our own observations.",
      ru: "Сверяем заявленную в каталоге «старую цену» с нашими собственными наблюдениями.",
    },
    "discount.noClaim": {
      az: "Yoxlanan {n} qiymət sətrində endirim iddiası yoxdur (köhnə qiymət göstərilməyib).",
      en: "None of the {n} checked price lines claims a discount (no old price is shown).",
      ru: "Ни в одной из {n} проверенных строк нет заявленной скидки (старая цена не указана).",
    },
    "verdict.subheli": { az: "Şübhəli", en: "Suspicious", ru: "Подозрительно" },
    "verdict.tesdiqlenmeyib": { az: "Təsdiqlənməyib", en: "Unverified", ru: "Не подтверждено" },
    "verdict.tesdiqlenib": { az: "Təsdiqlənib", en: "Verified", ru: "Подтверждено" },
    // «Hələ az müşahidə» AYRICA haldır: iddianın yalan olduğunu demir,
    // sadəcə yoxlaya bilmədiyimizi bildirir (P4).
    "verdict.az_musahide": {
      az: "Hələ az müşahidə",
      en: "Not enough observations yet",
      ru: "Пока мало наблюдений",
    },
    "trust.fewObservations": {
      az: "Hələ az müşahidə",
      en: "Too few observations",
      ru: "Мало наблюдений",
    },
    "trust.fewObservationsHint": {
      az: "Bu məhsulun qiymət tarixçəsi hələ qısadır — elan olunan köhnə qiyməti nə təsdiqləyə, nə təkzib edə bilirik.",
      en: "We have too little price history for this product — we can neither confirm nor refute the old price.",
      ru: "История цен этого товара пока короткая — мы не можем ни подтвердить, ни опровергнуть старую цену.",
    },
    "reason.tooFewObservations": {
      az: "Cəmi {n} müşahidə var — yoxlamaq üçün ən azı {need} lazımdır",
      en: "Only {n} observations — at least {need} are needed to verify",
      ru: "Всего {n} наблюдений — для проверки нужно минимум {need}",
    },
    "verdict.endirim_yoxdur": { az: "Endirim yoxdur", en: "No discount", ru: "Скидки нет" },
    "verdict.checked": { az: "Yoxlanıldı", en: "Checked", ru: "Проверено" },
    "health.works": { az: "işləyir", en: "working", ru: "работает" },

    // --------------------------------------------------- məhsul səhifəsi
    "product.best": { az: "Ən ucuz", en: "Cheapest", ru: "Самая дешёвая" },
    "product.bestValue": { az: "Ən sərfəli", en: "Best value", ru: "Выгоднее всего" },
    "product.noPrice": {
      az: "Bu məhsulun heç bir marketdə cari qiyməti yoxdur.",
      en: "This product has no current price at any supermarket.",
      ru: "У этого товара нет актуальной цены ни в одном магазине.",
    },
    "product.spread": {
      az: "{n} marketdə var — ən ucuz ilə ən bahalı arasında fərq {amount} ₼.",
      en: "Available at {n} supermarkets — the gap between cheapest and dearest is {amount} ₼.",
      ru: "Есть в {n} магазинах — разница между самой низкой и самой высокой ценой {amount} ₼.",
    },
    "product.onlyOne": {
      az: "Yalnız bir marketdə tapılıb — müqayisə üçün ikinci qiymət yoxdur.",
      en: "Found at only one supermarket — there is no second price to compare.",
      ru: "Найден только в одном магазине — второй цены для сравнения нет.",
    },
    "product.missingAt": { az: "{stores} kataloqunda tapılmadı.", en: "Not found in the {stores} catalogue.", ru: "Не найдено в каталоге {stores}." },
    "product.soonAt": { az: "{stores} — tezliklə.", en: "{stores} — coming soon.", ru: "{stores} — скоро." },
    "product.lowest": { az: "Ən aşağı", en: "Lowest", ru: "Минимум" },
    "product.usually": { az: "Adətən", en: "Usually", ru: "Обычно" },
    "product.basedOn": { az: "{n} müşahidəyə əsaslanır.", en: "Based on {n} observations.", ru: "Основано на {n} наблюдениях." },
    "product.notFound": { az: "Məhsul tapılmadı", en: "Product not found", ru: "Товар не найден" },
    "product.loadError": { az: "Məhsul datası yüklənmədi.", en: "Product data did not load.", ru: "Данные товара не загрузились." },

    // ----------------------------------------------------------- profil
    "profile.loadError": { az: "Profil yüklənmədi.", en: "The profile did not load.", ru: "Профиль не загрузился." },
    "profile.saving": { az: "Yadda saxlanılır…", en: "Saving…", ru: "Сохранение…" },
    "profile.serverError": { az: "Server xətası", en: "Server error", ru: "Ошибка сервера" },
    "profile.planError": { az: "Plan hesablanmadı.", en: "The plan could not be computed.", ru: "План не рассчитан." },
    "profile.noPlan": { az: "Plan qurmaq mümkün olmadı.", en: "It was not possible to build a plan.", ru: "Не удалось построить план." },
    "profile.singleVsSplit": { az: "Tək market / bölünmüş", en: "Single / split", ru: "Один магазин / раздельно" },
    "profile.settingsSub": {
      az: "Bu ayarlar bəzək deyil: tövsiyə məntiqi onlara görə dəyişir. Tək markete gedirsinizsə, 0.20 AZN üçün ikinci market təklif olunmayacaq.",
      en: "These settings are not decoration: the recommendation logic changes with them. If you shop at a single supermarket, a split trip will not be suggested.",
      ru: "Эти настройки — не украшение: логика рекомендации зависит от них. Если вы ходите в один магазин, раздельная покупка предлагаться не будет.",
    },
    "profile.split": { az: "Bölünmüş alış", en: "Split shopping", ru: "Покупка в двух магазинах" },
    "profile.single": { az: "Tək market", en: "Single supermarket", ru: "Один магазин" },
    "profile.diff": { az: "(fərq {amount})", en: "(difference {amount})", ru: "(разница {amount})" },
    "profile.notFound": { az: "tapılmadı", en: "not found", ru: "не найдено" },
    "profile.fits": { az: "sığır", en: "fits", ru: "укладывается" },
    "profile.over": { az: "{amount} AZN aşır", en: "over by {amount} AZN", ru: "превышение на {amount} AZN" },

    // --------------------------------------------------------- mənbədən çək
    "scrape.listError": { az: "Mənbə siyahısı yüklənmədi.", en: "The source list did not load.", ru: "Список источников не загрузился." },
    "scrape.pickFirst": { az: "Əvvəlcə mənbə seç.", en: "Pick a source first.", ru: "Сначала выберите источник." },
    "scrape.working": { az: "Çəkilir…", en: "Fetching…", ru: "Загрузка…" },

    "advisor.writing": { az: "Yazılır…", en: "Writing…", ru: "Пишет…" },

    // ============================================================ MƏHSUL SƏHİFƏSİ
    "product.searchPlaceholder": {
      az: "Məhsul və ya brend axtarın",
      en: "Search for a product or brand",
      ru: "Найдите товар или бренд",
    },
    "product.whereToBuy": { az: "Harada al", en: "Where to buy", ru: "Где купить" },
    "product.todayPrice": { az: "Bugünkü qiymət", en: "Today's price", ru: "Сегодняшняя цена" },
    "product.sizes": { az: "Ölçülər", en: "Sizes", ru: "Размеры" },
    "product.sameBrand": { az: "Eyni brenddən", en: "From the same brand", ru: "От того же бренда" },
    "product.similar": { az: "Oxşar məhsullar", en: "Similar products", ru: "Похожие товары" },
    "product.lowestPrice": { az: "Ən aşağı qiymət", en: "Lowest price", ru: "Самая низкая цена" },

    // =========================================================== AXTARIŞ SƏHİFƏSİ
    "search.filters": { az: "Filtrlər", en: "Filters", ru: "Фильтры" },
    "search.market": { az: "Market", en: "Supermarket", ru: "Магазин" },
    "search.category": { az: "Kateqoriya", en: "Category", ru: "Категория" },
    "search.maxPrice": { az: "Maksimum qiymət", en: "Maximum price", ru: "Максимальная цена" },
    "search.found": { az: "{n} məhsul tapıldı", en: "{n} products found", ru: "Найдено товаров: {n}" },
    "search.nothing": {
      az: "Bu filtrlərlə məhsul tapılmadı. Filtri yumşaldın və ya başqa söz axtarın.",
      en: "No product matches these filters. Loosen a filter or try another word.",
      ru: "По этим фильтрам ничего не найдено. Ослабьте фильтр или попробуйте другое слово.",
    },

    // ============================================================ MARKET SƏHİFƏSİ
    "store.discounts": { az: "Bu marketin endirimləri", en: "Discounts at this supermarket", ru: "Скидки этого магазина" },
    "store.priceCount": {
      az: "{n} məhsulun qiyməti bizdədir.",
      en: "We have prices for {n} products.",
      ru: "У нас есть цены на {n} товаров.",
    },
    "store.discountsSub": {
      az: "Kartın altındakı sətir eyni məhsulun digər marketlərdəki qiymətidir — endirim bu marketdə olsa da, ucuz qiymət başqa yerdə ola bilər.",
      en: "The line under each card is the same product's price at other supermarkets — the discount may be here, but the cheaper price elsewhere.",
      ru: "Строка под карточкой — цена того же товара в других магазинах: скидка может быть здесь, а цена ниже — в другом месте.",
    },
    "store.notFoundElsewhere": {
      az: "Digər marketlərdə tapılmadı",
      en: "Not found at other supermarkets",
      ru: "Не найдено в других магазинах",
    },

    // ================================================== BACKEND CÜMLƏLƏRİ
    // Server bu cümlələri AÇAR + PARAMETR şəklində göndərir (`reason_keys`,
    // `summary_keys`). Azərbaycanca variant serverdə də var - modelin promptu
    // azərbaycancadır və köhnə klientlər (MCP, n8n) həmin mətni oxuyur.

    // --- endirim yoxlamasının səbəbləri (app/analytics.py) ---
    "reason.tooDeep": {
      az: "Endirim {pct}% - ərzaqda bu dərinlikdə endirim praktiki olaraq olmur",
      en: "A {pct}% discount — a cut this deep practically does not happen in groceries",
      ru: "Скидка {pct}% — такой глубины в продуктах практически не бывает",
    },
    "reason.neverSeen": {
      az: "Bu məhsulu əvvəllər görməmişik - elan olunan köhnə qiyməti yoxlamaq üçün müqayisə nöqtəsi yoxdur",
      en: "We have not seen this product before — there is no reference point to check the claimed old price",
      ru: "Мы не видели этот товар раньше — нет точки сравнения, чтобы проверить заявленную старую цену",
    },
    "reason.inflated": {
      az: "Elan olunan köhnə qiymət {old} AZN, amma indiyədək gördüyümüz ən yüksək qiymət {max} AZN ({n} müşahidə)",
      en: "The claimed old price is {old} AZN, but the highest we have ever seen is {max} AZN ({n} observations)",
      ru: "Заявленная старая цена {old} AZN, но максимум, который мы видели, — {max} AZN ({n} наблюдений)",
    },
    "reason.confirmed": {
      az: "Bu məhsulu əvvəllər {max} AZN-ə görmüşük - elan olunan köhnə qiymət ({old}) həqiqətə uyğundur",
      en: "We have seen this product at {max} AZN before — the claimed old price ({old}) matches reality",
      ru: "Мы видели этот товар по {max} AZN — заявленная старая цена ({old}) соответствует действительности",
    },
    "reason.inconclusive": {
      az: "Tarixçədə ən yüksək qiymət {max} AZN, iddia isə {old} AZN - nə təsdiqləyə, nə təkzib edə bilirik",
      en: "The highest price in our history is {max} AZN against a claim of {old} AZN — we can neither confirm nor refute it",
      ru: "Максимум в истории — {max} AZN, а заявлено {old} AZN — мы не можем ни подтвердить, ни опровергнуть",
    },
    "reason.cheaperElsewhere": {
      az: "Endirimdən asılı olmayaraq {store} marketində daha ucuzdur: {price} AZN",
      en: "Discount aside, it is cheaper at {store}: {price} AZN",
      ru: "Независимо от скидки, в {store} дешевле: {price} AZN",
    },

    // --- profil xülasəsi (app/profile.py) ---
    "sum.household": { az: "{n} nəfərlik ev", en: "household of {n}", ru: "семья из {n} чел." },
    "sum.budget": { az: "həftəlik büdcə {amount} AZN", en: "weekly budget {amount} AZN", ru: "недельный бюджет {amount} AZN" },
    "sum.oneStore": { az: "yalnız bir markete gedir", en: "visits only one supermarket", ru: "ходит только в один магазин" },
    "sum.maxStores": { az: "ən çox {n} markete gedə bilir", en: "can visit up to {n} supermarkets", ru: "может посетить до {n} магазинов" },
    "sum.unitPrice": { az: "kq/litr qiymətinə baxır", en: "compares by kg/litre price", ru: "смотрит цену за кг/литр" },
    "sum.avoid": { az: "istəmir: {words}", en: "avoids: {words}", ru: "избегает: {words}" },

    // ============================================================== KATEQORİYALAR
    // Bazada AZƏRBAYCANCA saxlanılır (data dəyişmir), tərcümə yalnız ekrandadır.
    "cat.süd məhsulları": { az: "süd məhsulları", en: "dairy", ru: "молочные продукты" },
    "cat.çörək və taxıl": { az: "çörək və taxıl", en: "bread and grains", ru: "хлеб и крупы" },
    "cat.ət və balıq": { az: "ət və balıq", en: "meat and fish", ru: "мясо и рыба" },
    "cat.meyvə-tərəvəz": { az: "meyvə-tərəvəz", en: "fruit and vegetables", ru: "фрукты и овощи" },
    "cat.içkilər": { az: "içkilər", en: "drinks", ru: "напитки" },
    "cat.şirniyyat": { az: "şirniyyat", en: "sweets", ru: "сладости" },
    "cat.quru ərzaq": { az: "quru ərzaq", en: "dry goods", ru: "бакалея" },
    "cat.yağ və souslar": { az: "yağ və souslar", en: "oils and sauces", ru: "масла и соусы" },
    "cat.təmizlik və gigiyena": { az: "təmizlik və gigiyena", en: "cleaning and hygiene", ru: "уборка и гигиена" },
    "cat.digər": { az: "digər", en: "other", ru: "прочее" },
  };

  function normalize(lang) {
    return SUPPORTED.includes(lang) ? lang : "az";
  }

  let current = normalize(
    (() => {
      try {
        return localStorage.getItem(STORAGE_KEY);
      } catch {
        // Şəxsi rejimdə `localStorage` istisna ata bilər - dil sadəcə
        // yadda saxlanılmır, səhifə isə işləməyə davam edir.
        return null;
      }
    })()
  );

  /**
   * Açar -> cari dildəki mətn.
   *
   * `vars` sadə əvəzləmə üçündür: `t("search.found", {n: 5})`.
   * Tapılmayan açar üçün AZƏRBAYCANCA variant qaytarılır - ekranda açar adı
   * («search.found») görünməsindənsə, tərcümə olunmamış mətn görünsün.
   */
  function t(key, varsOrFallback) {
    // İkinci arqument ya dəyişənlər obyekti, ya da EHTİYAT MƏTNDİR.
    // Ehtiyat variant kateqoriyalar üçün lazımdır: bazaya yeni kateqoriya
    // düşsə, lüğətdə açar olmaya bilər - onda ekranda azərbaycanca adı qalır,
    // açar adı («cat.yeni») yox.
    const fallback = typeof varsOrFallback === "string" ? varsOrFallback : null;
    const vars = fallback ? null : varsOrFallback;
    const giriş = DICT[key];
    let mətn = giriş ? giriş[current] || giriş.az : fallback || key;
    if (vars) {
      for (const [ad, dəyər] of Object.entries(vars)) {
        mətn = mətn.split(`{${ad}}`).join(dəyər);
      }
    }
    return mətn;
  }

  /**
   * `data-i18n` və `data-i18n-attr` işarələnmiş elementləri tərcümə edir.
   *
   * `data-i18n-attr` formatı: "placeholder:search.placeholder;aria-label:nav.x"
   */
  function apply(root) {
    const kök = root || document;
    kök.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    kök.querySelectorAll("[data-i18n-attr]").forEach((el) => {
      el.dataset.i18nAttr.split(";").forEach((cüt) => {
        const [atr, açar] = cüt.split(":").map((s) => s.trim());
        if (atr && açar) el.setAttribute(atr, t(açar));
      });
    });
    if (document.title && DICT[`title.${document.body.dataset.page}`]) {
      document.title = t(`title.${document.body.dataset.page}`);
    }
  }

  function setLang(lang) {
    current = normalize(lang);
    try {
      localStorage.setItem(STORAGE_KEY, current);
    } catch {
      /* yaddaş yoxdursa seçim yalnız bu səhifə üçün qalır */
    }
    document.documentElement.lang = current;
    apply();
    // Dinamik modullar öz hissəsini yenidən çəkir - səhifə yenilənmir.
    document.dispatchEvent(new CustomEvent("basketiq:lang", { detail: current }));
  }

  function getLang() {
    return current;
  }

  globalThis.I18n = { t, apply, setLang, getLang, SUPPORTED, DICT };
  globalThis.t = t;

  // Dil düyməsi hər səhifədə eyni qaydada işləyir.
  function bindSwitcher() {
    document.querySelectorAll("[data-lang]").forEach((btn) => {
      btn.setAttribute("aria-selected", String(btn.dataset.lang === current));
      btn.addEventListener("click", () => {
        setLang(btn.dataset.lang);
        document.querySelectorAll("[data-lang]").forEach((b) => {
          b.setAttribute("aria-selected", String(b.dataset.lang === current));
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.documentElement.lang = current;
    apply();
    bindSwitcher();
  });
})();
