"""
Prompt-lar bir yerdə saxlanılır.

PROMPT_VERSION vacibdir: prompt dəyişəndə keş avtomatik etibarsız olur.
Əks halda köhnə (səhv) nəticələr diskdən qayıdar və sən prompt-un işlədiyini
sanarsan - bu, ən çətin tapılan səhvlərdən biridir.
"""

from langchain_core.prompts import ChatPromptTemplate

PROMPT_VERSION = "extract-v3"

# ÖLÇÜLMÜŞ FAKT (tools/profile_llm.py):
#   prompt emalı  : 293 token/saniyə  -> sürətli
#   cavab yazması :   5 token/saniyə  -> ƏSAS ƏNGƏL
#
# Yəni GPU-suz maşında vaxtı prompt yox, CAVABIN UZUNLUĞU müəyyən edir.
# Ona görə cavabı maksimum qısaldırıq:
#   - açar adları tək hərfdir       ("size_value" -> "v")
#   - kateqoriya rəqəmlə verilir    ("süd məhsulları" -> 1)
#   - boşluq və girinti qadağandır
# Nəticə: 50 token -> ~20 token, yəni ~2.5 dəfə sürətli.
#
# Qısa açarlar sonra ai/chains.py-də tam adlara açılır və
# PydanticOutputParser onları yoxlayır - yəni etibarlılıq itmir.
#
# DİQQƏT: burada TƏK mötərizə istifadə olunur. Bu mətn şablonun içində deyil,
# .partial() ilə HAZIR DƏYƏR kimi ötürülür - LangChain onu yenidən şablon kimi
# oxumur. Qoşa mötərizə yazsaq, modelə hərfi "{{" görünər.
COMPACT_FORMAT_INSTRUCTIONS = """Cavab formatı (boşluqsuz, tək sətir):
{"n":"ad","b":"brend və ya null","v":rəqəm və ya null,"u":"kg" və ya "g" və ya "l" və ya "ml" və ya "pcs" və ya null,"c":kateqoriya nömrəsi}

Vahid KİÇİK hərflə yazılmalıdır: "l", "kg", "g", "ml", "pcs"."""

EXTRACTION_SYSTEM = """Sən supermarket kataloqlarından məlumat çıxaran dəqiq bir sistemsən.

Sənə OCR ilə oxunmuş BİR kataloq sətri verilir. Sənin işin bu sətirdən məhsul
haqqında atributları ayırıb JSON formatında qaytarmaqdır.

QAYDALAR:
1. Qiymət SORUŞULMUR. Sətirdəki rəqəmləri cavaba salma.
2. "n" - məhsulun ümumi adı, brend və ölçü OLMADAN.
   "Süd Milla 2.5% 1 L" -> "süd"
   "Günəbaxan yağı Sola 1.8 L" -> "günəbaxan yağı"
3. "b" - brend adı. Yoxdursa null.
4. "v" və "u" - qablaşdırma ölçüsü.
   "1 L" -> 1, "l"      "500 q" -> 500, "g"      "1 kq" -> 1, "kg"
   "10 ədəd" -> 10, "pcs"
   Faiz (2.5%) ölçü DEYİL. Ölçü yoxdursa hər ikisi null.
5. "c" - kateqoriya NÖMRƏSİ:
{categories}
6. OCR səhv hərflər yaza bilər. Kontekstdən düz oxu, amma uydurma.
7. Sətir məhsul deyilsə (reklam, ünvan, tarix), "n" sahəsinə "" yaz.

Yalnız JSON qaytar, başqa heç nə yazma.

{format_instructions}"""

EXTRACTION_HUMAN = """Kataloq sətri:
{line}"""

EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", EXTRACTION_SYSTEM),
        ("human", EXTRACTION_HUMAN),
    ]
)


# --------------------------------------------------------------------- MATCHING

MATCH_PROMPT_VERSION = "match-v2"

# Cavab CƏMİ 1 rəqəmdir: {"s":1} və ya {"s":0}
# 4.5 token/saniyə sürətlə bu ~1-2 saniyə deməkdir, halbuki uzun izah 10 saniyə olardı.
# Modelin "niyə" izah etməsinə ehtiyacımız yoxdur - bizə yalnız qərar lazımdır.
MATCH_SYSTEM = """Sən supermarket məhsullarını müqayisə edən dəqiq bir sistemsən.

Sənə iki məhsul verilir. Onların EYNİ məhsul olub-olmadığını müəyyən et.

EYNİ sayılır:
- eyni məhsul, fərqli yazılış ("süd Milla" və "Milla süd")
- eyni məhsul, kiçik fərqli təsvir ("günəbaxan yağı" və "günəbaxan yağ")
- biri ÜMUMİ, digəri KONKRET ad ("yumurta" və "toyuq yumurtası";
  "düyü" və "basmati düyüsü") - əgər konkret ad ümumi adın adi növüdürsə

FƏRQLİ sayılır:
- fərqli brend (Milla ≠ President)
- fərqli məhsul növü (süd ≠ qatıq, düyü ≠ makaron)
- fərqli dad/növ (çiyələkli yoqurt ≠ şaftalılı yoqurt)
- fərqli yağlılıq və ya tərkib açıq şəkildə göstərilibsə

Şübhə edirsənsə 0 yaz. Səhv birləşdirmək səhv ayırmaqdan daha pisdir.

Cavab formatı: {{"s":1}} əgər eynidirsə, {{"s":0}} əgər fərqlidirsə.
Başqa heç nə yazma."""
# QOŞA mötərizəyə diqqət: bu mətn şablonun ÖZÜNDƏDİR, ona görə LangChain onu
# dəyişən adı kimi oxumasın deyə {{ }} yazılır.
# COMPACT_FORMAT_INSTRUCTIONS-da isə TƏK mötərizədir, çünki o, .partial() ilə
# hazır dəyər kimi ötürülür və yenidən şablon kimi oxunmur.

MATCH_HUMAN = """1: {product_a}
2: {product_b}"""

MATCH_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", MATCH_SYSTEM),
        ("human", MATCH_HUMAN),
    ]
)


# --------------------------------------------------------------------- ADVISOR

ADVISOR_PROMPT_VERSION = "advisor-v3"

# Bu, layihədə istifadəçinin GÖZLƏDİYİ yeganə çağırışdır - ona görə astream().
# Rəqəmlər Python-da hesablanıb faktlar blokunda hazır verilir; modelin işi
# yalnız onları cümləyə çevirməkdir.
ADVISOR_SYSTEM = """Sən alış-veriş üzrə praktik məsləhətçisən.

Sənə səbətin market müqayisəsi HAZIR RƏQƏMLƏRLƏ verilir.

QAYDALAR:
1. HEÇ NƏ HESABLAMA. Yalnız verilən rəqəmləri istifadə et.
   Yeni rəqəm uydurma, cəm çıxarma, faiz hesablama.
2. Maksimum 4 qısa cümlə yaz.
3. Əvvəlcə hansı marketin seçilməli olduğunu de.
4. Sonra ən böyük qiymət fərqi olan 1-2 məhsulu qeyd et.
5. Bir market məhsulun hamısını satmırsa, bunu MÜTLƏQ xəbərdarlıq kimi yaz -
   onun cəmi ucuz görünə bilər, çünki çatışmayan məhsul sayılmayıb.
6. Yalnız bir məhsula görə ayrı markete getmək sərfəli deyilsə, bunu de.
6a. İSTİFADƏÇİ sətri varsa, tövsiyəni ona uyğunlaşdır: tək markete gedən
   adama iki marketi bölüşdürmə, büdcəsi varsa cəmi onunla tutuşdur.
7. Sadə danışıq dilində yaz. Başlıq, siyahı, markdown işarəsi istifadə etmə.
8. Yalnız SON cavabı yaz. Düşüncəni, addım-addım təhlili, <think> bloklarını
   və "gəlin baxaq" tipli girişi yazma - birbaşa tövsiyə ilə başla.

Azərbaycan dilində cavab ver."""

ADVISOR_HUMAN = """{facts}

Yuxarıdakı rəqəmlərə əsasən qısa tövsiyə yaz."""

ADVISOR_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", ADVISOR_SYSTEM),
        ("human", ADVISOR_HUMAN),
    ]
)


# ---------------------------------------------------------------- MƏHSUL QEYDİ

PRODUCT_NOTE_PROMPT_VERSION = "product-note-v1"

# NİYƏ «RƏY» DEYİL, «QEYD»?
#
# Trolley-nin məhsul səhifəsində istifadəçi rəyləri bölməsi var. Bizdə rəy
# YOXDUR - nə istifadəçi hesabı, nə rəy cədvəli, nə də bir dənə real müştəri.
# Modelə «rəy yaz» desək, o, uydurar: «əla məhsuldur, ailəm çox bəyəndi».
# Bu, saxta rəydir - istifadəçini birbaşa yanıldan ən pis hallardan biri.
#
# Ona görə bölmənin ADI da, PROMPT-u da dəyişdirilib: model yalnız BİZİM
# hesabladığımız qiymət faktlarını cümləyə çevirir. Yəni burada model
# «məhsul haqqında» yox, «bu məhsulun qiymət mənzərəsi haqqında» yazır.
PRODUCT_NOTE_SYSTEM = """Sən qiymət müqayisəsi üzrə köməkçisən.

Sənə bir məhsulun marketlərdəki qiymətləri HAZIR RƏQƏMLƏRLƏ verilir.

QAYDALAR:
1. HEÇ NƏ HESABLAMA və yeni rəqəm uydurma. Yalnız verilən rəqəmləri işlət.
2. Maksimum 2 qısa cümlə.
3. MÜŞTƏRİ RƏYİ YAZMA. «Dadlıdır», «keyfiyyətlidir», «tövsiyə edirəm»,
   «alıcılar bəyənir» kimi ifadələr QADAĞANDIR - sənin məhsulu dadmaq və ya
   alıcıları tanımaq imkanın yoxdur.
4. Yalnız qiymətdən danış: harada ucuzdur, fərq nə qədərdir, hansı ölçü
   vahid qiymətinə görə sərfəlidir, endirim varmı.
5. Fakt blokunda olmayan heç nə haqqında yazma. Məhsulun tərkibi, dadı,
   istehsalçısı və istifadəsi barədə məlumatımız yoxdur.
6. Sadə danışıq dilində yaz. Başlıq, siyahı, markdown işarəsi işlətmə.
7. Yalnız SON cavabı yaz - düşüncəni və <think> bloklarını yazma.

Azərbaycan dilində cavab ver."""

PRODUCT_NOTE_HUMAN = """{facts}

Yuxarıdakı rəqəmlərə əsasən bu məhsulun qiyməti barədə qısa qeyd yaz."""

PRODUCT_NOTE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", PRODUCT_NOTE_SYSTEM),
        ("human", PRODUCT_NOTE_HUMAN),
    ]
)
