"""
Model cavabından "düşünmə" (chain-of-thought) hissəsinin təmizlənməsi.

NİYƏ LAZIMDIR?
Dil modeli bəzən cavabdan əvvəl öz-özü ilə danışır:

    <think>Okay, let me work through this. Araz 19.65, Bravo 16.54...</think>
    Araz marketini seçin, çünki...

Bu mətn istifadəçi üçün deyil - o, modelin daxili qeydidir. Ekranda görünsə:
  - tövsiyə uzun və qarışıq görünür;
  - model natamam düşüncəsini "fakt" kimi yazır ("Bravo ucuzdur" - halbuki
    sonra fikrini dəyişir);
  - rəqəm yoxlaması (`verify_numbers`) düşünmədəki xam rəqəmləri də sayır və
    yalan xəbərdarlıq verir.

HARADA TƏMİZLƏNİR?
Backend-də, `ai/advisor.py` içində - yəni mətn frontend-ə çatmamışdan ƏVVƏL.
Xam model cavabı heç vaxt brauzerə göndərilmir.

NİYƏ İKİ MEXANİZM VAR?
Cavab token-token axır (SSE), yəni `<think>` etiketi iki hissəyə bölünə bilər:
birinci parçada `<thi`, ikincidə `nk>`. Adi `re.sub()` bunu tuta bilməz - o,
tam mətn görməlidir. Ona görə:

  1. `ReasoningFilter` - AXIN üçün vəziyyət maşını. Etiketin yarısı gələndə
     onu buferdə saxlayır, tam gələndə blokun sonuna qədər atır.
  2. `strip_reasoning()` - TAM mətn üçün son yoxlama. Axın bitəndə bir daha
     işlədilir: "Cavab:" kimi son-cavab markerini tapıb ondan əvvəlkini atır.
     Bunu axında etmək mümkün deyil (marker sonda gəlir), ona görə `done`
     hadisəsi ilə UI-dakı mətn təmiz versiya ilə əvəz olunur.

DİQQƏT: yalnız BLOK STRUKTURU silinir.
"...bunun səbəbi (reasoning) sadədir" kimi normal cümlədəki söz toxunulmazdır -
marker yalnız sətrin əvvəlində və ikinöqtə ilə tanınır.
"""

import re

# --- Etiketli bloklar: <think>...</think>, [thinking]...[/thinking] ---
#
# Adlar modeldən modelə dəyişir (qwen `<think>`, bəziləri `<reasoning>`),
# ona görə hamısını bir siyahıda saxlayırıq.
_BLOCK_NAMES = ("think", "thinking", "thought", "reasoning", "analysis", "scratchpad")

_TAG_BLOCK_RE = re.compile(
    r"<(?P<name>" + "|".join(_BLOCK_NAMES) + r")\b[^>]*>.*?</(?P=name)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_BRACKET_BLOCK_RE = re.compile(
    r"\[(?P<name>" + "|".join(_BLOCK_NAMES) + r")\].*?\[/(?P=name)\]",
    re.IGNORECASE | re.DOTALL,
)

# Bağlanmamış açılış etiketi: model `<think>` yazıb bağlamadan kəsilib.
# Qalan hər şey düşünmədir - atılır.
_UNCLOSED_TAG_RE = re.compile(
    r"<(?:" + "|".join(_BLOCK_NAMES) + r")\b[^>]*>.*\Z",
    re.IGNORECASE | re.DOTALL,
)

# --- Sətir başında etiket: "Reasoning: ..." ---
#
# `^` + `re.MULTILINE` VACİBDİR: cümlənin ortasındakı söz silinməməlidir.
_LABEL_LINE_RE = re.compile(
    r"^[ \t]*(?:" + "|".join(_BLOCK_NAMES) + r"|chain[- ]of[- ]thought|düşüncə|təhlil)"
    r"[ \t]*:[^\n]*(?:\n(?![ \t]*\n)[^\n]*)*",
    re.IGNORECASE | re.MULTILINE,
)

# --- Son cavab markeri ---
#
# Model düşünüb sonra "Cavab:" yazırsa, ondan ƏVVƏLKİ hər şey atılır.
# Sətir başında olmalıdır ki, "...qısa cavab: bəli" kimi cümlə zədələnməsin.
_FINAL_ANSWER_RE = re.compile(
    r"^[ \t]*(?:final answer|answer|cavab|tövsiyə|nəticə)[ \t]*:[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)


def strip_reasoning(text: str) -> str:
    """
    Tam mətndən düşünmə bloklarını çıxarır.

    Ardıcıllıq vacibdir: əvvəlcə etiketli bloklar (ən dəqiq forma), sonra
    sətir etiketləri, ən axırda son-cavab markeri.
    """
    if not text:
        return ""

    cleaned = _TAG_BLOCK_RE.sub("", text)
    cleaned = _BRACKET_BLOCK_RE.sub("", cleaned)
    cleaned = _UNCLOSED_TAG_RE.sub("", cleaned)
    cleaned = _LABEL_LINE_RE.sub("", cleaned)

    # Son cavab markeri varsa, SONUNCUsundan sonrakını götürürük:
    # model bəzən "Cavab:" yazıb yenidən düşünür, sonra əsl cavabı verir.
    matches = list(_FINAL_ANSWER_RE.finditer(cleaned))
    if matches:
        candidate = cleaned[matches[-1].end():].strip()
        # Marker sonuncu simvoldursa arxasında mətn yoxdur - onda mətni
        # olduğu kimi saxlayırıq, yoxsa istifadəçiyə boş ekran qalar.
        if candidate:
            cleaned = candidate

    return _tidy(cleaned)


def _tidy(text: str) -> str:
    """Blok silindikdən sonra qalan artıq boşluqları yığışdırır."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------- axın filtri

# Filtrin "gözlədiyi" bütün marker başlanğıcları. Buferdə saxlanılacaq maksimum
# uzunluq buradan hesablanır - yəni sabit əl ilə yazılmır, siyahı dəyişsə
# özü uyğunlaşır.
_OPENERS = tuple(
    [f"<{name}" for name in _BLOCK_NAMES] + [f"[{name}]" for name in _BLOCK_NAMES]
)
_MAX_OPENER = max(len(o) for o in _OPENERS) + 1  # +1: `>` üçün
# Bağlanış `</thinking >` kimi boşluqlu da ola bilər - ehtiyat pay qoyulur
_MAX_CLOSER = max(len(name) for name in _BLOCK_NAMES) + 6


class ReasoningFilter:
    """
    Token axını üçün vəziyyət maşını.

    İSTİFADƏ:
        f = ReasoningFilter()
        for chunk in stream:
            out = f.feed(chunk)   # təmiz hissə (boş ola bilər)
        out += f.flush()          # axın bitdi

    NECƏ İŞLƏYİR?
    İki vəziyyət var: "kənarda" və "blokun içində".

    Kənarda olanda mətn dərhal buraxılır - AMMA sonundan kiçik bir hissə
    saxlanılır. Səbəb: axırıncı simvollar yarımçıq etiketin başlanğıcı ola
    bilər (`...qiymət <thi`). Onları buraxsaq, etiket ekranda görünərdi.
    Saxlanılan hissə ~12 simvoldur - istifadəçi bunu hiss etmir.

    Blokun içində olanda heç nə buraxılmır: bağlanış etiketi gələnə qədər
    hər şey atılır.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._closing: str | None = None  # blokun içindəyiksə - gözlənilən bağlanış

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        out: list[str] = []

        while True:
            if self._closing is not None:
                # Blokun içindəyik: bağlanışı axtarırıq
                match = self._closing.search(self._buffer)
                if match is None:
                    # Hələ gəlməyib. Bağlanışın yarısı buferin sonunda ola
                    # bilər - yalnız o qədərini saxlayırıq, qalanı atırıq.
                    self._buffer = self._buffer[-_MAX_CLOSER:]
                    return "".join(out)
                self._buffer = self._buffer[match.end():]
                self._closing = None
                continue

            opener = self._find_opener()
            if opener is None:
                break

            start, end, closing = opener
            out.append(self._buffer[:start])
            self._buffer = self._buffer[end:]
            self._closing = closing

        # Kənardayıq: təhlükəsiz hissəni buraxırıq, şübhəli quyruğu saxlayırıq
        safe = len(self._buffer) - self._pending_tail()
        if safe > 0:
            out.append(self._buffer[:safe])
            self._buffer = self._buffer[safe:]
        return "".join(out)

    def flush(self) -> str:
        """
        Axın bitdi - buferdə qalanı qaytarır.

        Blokun içində qalmışıqsa (model `<think>` yazıb bağlamayıb), qalan
        mətn tamamilə düşünmədir: boş qaytarırıq.
        """
        if self._closing is not None:
            self._buffer = ""
            return ""
        rest, self._buffer = self._buffer, ""
        return rest

    # -------------------------------------------------------------- daxili

    def _find_opener(self) -> tuple[int, int, re.Pattern] | None:
        """Buferdəki ƏN ERKƏN tam açılış etiketini tapır."""
        lowered = self._buffer.lower()
        best: tuple[int, int, re.Pattern] | None = None

        for name in _BLOCK_NAMES:
            # <think ...>
            match = re.search(rf"<{name}\b[^>]*>", lowered)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), match.end(), re.compile(rf"</{name}\s*>", re.I))
            # [thinking]
            index = lowered.find(f"[{name}]")
            if index != -1 and (best is None or index < best[0]):
                best = (index, index + len(name) + 2,
                        re.compile(rf"\[/{name}\]", re.I))

        return best

    def _pending_tail(self) -> int:
        """
        Buferin sonunda neçə simvol saxlanmalıdır?

        İki hal var:
          `...qiymət <thi`       -> etiketin adı yarımçıqdır
          `...qiymət <think foo` -> ad tamdır, amma `>` hələ gəlməyib

        Hər ikisində quyruq saxlanılır, əks halda yarımçıq etiket ekranda
        görünərdi. Saxlanılan hissə ən çoxu ~12 simvoldur.
        """
        tail = self._buffer[-_MAX_OPENER:].lower()
        for size in range(len(tail), 0, -1):
            piece = tail[-size:]
            if any(opener.startswith(piece) or piece.startswith(opener)
                   for opener in _OPENERS):
                return size
        return 0
