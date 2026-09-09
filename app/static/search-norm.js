// AXTARIŞ NORMALLAŞDIRMASI — brauzer tərəfi (M0).
//
// CƏDVƏL `app/search_norm.py`-dən GƏLİR və orada YEGANƏ mənbədir.
// Burada nüsxəsi var, çünki brauzer Python-u işlədə bilmir; iki nüsxənin
// ayrılmasının qarşısını `tests/test_search_norm.py` alır - o, bu faylı
// oxuyub cədvəli hərfbəhərf tutuşdurur. Fərq yaransa test düşür.
//
// Cədvəli əl ilə dəyişmə: `python -m tools.sync_fold_table` onu Python-dakı
// mənbədən yenidən yazır.
//
// İKİ QAYDA (Python tərəfi ilə eyni):
//   1. Əvəzləmə 1:1-dir - uzunluq dəyişmir, ona görə normallaşmış mətndəki
//      mövqe orijinal mətndəki mövqe ilə üst-üstə düşür (işıqlandırma üçün).
//   2. Əvvəl fold, sonra kiçik hərf: «I» və «İ» hər ikisi ASCII «i»-yə düşür
//      və nəticə brauzerin lokalından asılı olmur.

// --- FOLD_MAP başlanğıc (avtomatik yazılır) ---
const FOLD_MAP = {
  "ə": "e", "Ə": "e",
  "ı": "i", "I": "i", "İ": "i",
  "ö": "o", "Ö": "o",
  "ü": "u", "Ü": "u",
  "ş": "s", "Ş": "s",
  "ç": "c", "Ç": "c",
  "ğ": "g", "Ğ": "g",
};
// --- FOLD_MAP son ---

/**
 * Mətni müqayisə formasına salır. UZUNLUQ DƏYİŞMİR.
 *
 * `toLowerCase()` DEYİL, `toLowerCase("en-US")` də deyil: fold-dan sonra
 * mətndə yalnız ASCII hərflər qalır, ona görə adi `toLowerCase()` hər
 * platformada eyni nəticə verir.
 */
function foldText(text) {
  if (!text) return "";
  let out = "";
  for (const ch of String(text)) out += FOLD_MAP[ch] ?? ch;
  return out.toLowerCase();
}

/** Sorğunu sözlərə bölür - çoxsözlü axtarış VƏ məntiqi ilə işləyir. */
function foldTokens(text) {
  return foldText(text)
    .replace(/-/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}
