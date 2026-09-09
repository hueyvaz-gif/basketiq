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

    "nav.panelSelect": { az: "Panel seçimi", en: "Panel selection", ru: "Выбор панели" },
    "nav.user": { az: "İstifadəçi", en: "User", ru: "Пользователь" },
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
    "deals.available": { az: "Mövcuddur", en: "Available at", ru: "В наличии" },
    "deals.saving": { az: "qənaət", en: "saved", ru: "экономия" },
    "deals.onlyAt": { az: "Yalnız {store}-də tapılıb", en: "Found only at {store}", ru: "Найдено только в {store}" },

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
    "compare.sub": {
      az: "Hər sətirdə ən ucuz qiymət ✓ nişanı və çərçivə ilə işarələnib.",
      en: "In each row the lowest price is marked with a ✓ and a border.",
      ru: "В каждой строке самая низкая цена отмечена значком ✓ и рамкой.",
    },
    "compare.addLabel": { az: "Məhsul axtar və səbətə əlavə et", en: "Search a product and add it to the basket", ru: "Найдите товар и добавьте в корзину" },
    "compare.addPlaceholder": { az: "süd, düyü, yağ…", en: "milk, rice, oil…", ru: "молоко, рис, масло…" },
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
  function t(key, vars) {
    const giriş = DICT[key];
    let mətn = giriş ? giriş[current] || giriş.az : key;
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
