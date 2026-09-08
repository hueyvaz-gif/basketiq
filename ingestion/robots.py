"""
robots.txt oxuyucusu — RFC 9309 semantikası.

NİYƏ STANDART KİTABXANA İŞLƏMİR?

`urllib.robotparser`-də bu layihə üçün həlledici olan İKİ səhv var. Hər ikisi
ölçülüb (2026-09-08, aşağıdakı rəqəmlər real cavablardır):

1. **Öz adı ilə gedir.** `RobotFileParser.read()` faylı urllib ilə çəkir və
   özünü `Python-urllib/3.x` kimi təqdim edir. `umico.az` və
   `bravosupermarket.az` bu ada **403** qaytarır. Kitabxana isə 403-ü
   "bütün sayt qadağandır" kimi qeyd edir (`disallow_all = True`).
   Nəticə: `Allow: /` yazan sayt bizim kodda QADAĞA görünürdü — və README-də
   Bravo məhz belə "qadağalı" kimi qeydə düşmüşdü.

2. **Birinci uyğunluğu götürür, ən uzununu yox.** `arazmarket.az/robots.txt`:

       Allow: /
       Disallow: /api/

   `urllib` sətirləri sıra ilə yoxlayır, `Allow: /` hər şeyə uyğun gəlir və
   dərhal "icazə var" deyir — yəni `Disallow: /api/` HEÇ VAXT işə düşmür.
   RFC 9309 isə açıq deyir: **ən spesifik (ən uzun) qayda qalib gəlir**.
   Bu fərq bizim üçün nəzəri deyil: Araz-ın data ünvanı məhz `/api/`-dir.

Yəni standart kitabxana bir marketi haqsız yerə qadağalı, başqasının qadağasını
isə görünməz edirdi. Hər iki səhv eyni istiqamətə işləmir — biri bizi lazımsız
məhdudlaşdırır, digəri qadağanı pozmağa aparır. İkincisi daha təhlükəlidir.

BU MODUL ŞƏBƏKƏYƏ ÇIXMIR. `parse()` mətn qəbul edir, `allows()` yol qaytarır —
ona görə testlər real saytdan asılı deyil. Faylı çəkmək çağıranın işidir.
"""

import re
import urllib.parse as urlparse
from dataclasses import dataclass

__all__ = ["Rule", "RobotsRules", "robots_url_for"]


def robots_url_for(url: str) -> str:
    """Verilmiş URL-in hostuna aid robots.txt ünvanı."""
    parts = urlparse.urlparse(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


@dataclass(frozen=True)
class Rule:
    allow: bool
    pattern: str

    @property
    def specificity(self) -> int:
        """RFC 9309: uyğunluqlar arasında ən uzun `pattern` qalib gəlir."""
        return len(self.pattern)


def _pattern_to_regex(pattern: str) -> re.Pattern[str]:
    """
    robots.txt naxışını regex-ə çevirir.

    Yalnız iki xüsusi işarə var: `*` (istənilən ardıcıllıq) və sonda `$`
    (yolun sonu). Qalan hər şey hərfi mənada götürülür.
    """
    anchored_end = pattern.endswith("$")
    body = pattern[:-1] if anchored_end else pattern
    escaped = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.compile("^" + escaped + ("$" if anchored_end else ""))


class RobotsRules:
    """Bir user-agent üçün seçilmiş qayda dəsti."""

    def __init__(
        self,
        rules: list[Rule] | None = None,
        *,
        allow_all: bool = False,
        disallow_all: bool = False,
    ) -> None:
        self.rules = rules or []
        self.allow_all = allow_all
        self.disallow_all = disallow_all
        self._compiled = [(_pattern_to_regex(r.pattern), r) for r in self.rules]

    # ------------------------------------------------------------------ parse

    @classmethod
    def parse(cls, text: str, user_agent: str) -> "RobotsRules":
        """
        robots.txt mətnindən bizə aid qrupu seçir.

        Qrup seçimi: `User-agent` dəyəri bizim adımızın içində keçirsə, o qrup
        götürülür (ən uzun uyğunluq qalib gəlir); heç biri uyğun gəlmirsə `*`
        qrupu. Hər ikisi yoxdursa qayda yoxdur = icazə var.
        """
        groups: dict[str, list[Rule]] = {}
        current: list[str] = []
        # `User-agent` sətirləri ardıcıl gələndə hamısı EYNİ qrupa aiddir;
        # aralarında qayda görünəndən sonra yeni qrup başlayır.
        expecting_agents = False

        for raw in text.splitlines():
            stripped = raw.split("#", 1)[0].strip()
            if not stripped or ":" not in stripped:
                continue
            field, _, value = stripped.partition(":")
            field = field.strip().lower()
            value = value.strip()

            if field == "user-agent":
                if not expecting_agents:
                    current = []
                    expecting_agents = True
                current.append(value.lower())
                groups.setdefault(value.lower(), [])
            elif field in ("allow", "disallow"):
                expecting_agents = False
                if not current:
                    continue
                # Boş `Disallow:` heç nəyi qadağan etmir - qayda deyil.
                if field == "disallow" and value == "":
                    continue
                if value == "":
                    continue
                for agent in current:
                    groups.setdefault(agent, []).append(
                        Rule(allow=(field == "allow"), pattern=value)
                    )

        ua_low = user_agent.lower()
        best_key: str | None = None
        for agent in groups:
            if agent == "*":
                continue
            if agent and agent in ua_low:
                if best_key is None or len(agent) > len(best_key):
                    best_key = agent
        if best_key is None and "*" in groups:
            best_key = "*"

        return cls(list(groups.get(best_key, [])) if best_key else [])

    # ------------------------------------------------------------------ sorğu

    def allows(self, url_or_path: str) -> bool:
        """
        Bu yol çəkilə bilərmi?

        Qərar RFC 9309 üzrədir: uyğun gələn qaydalar arasında ən uzun naxış
        qalib gəlir; uzunluq bərabər olanda `Allow` üstündür (standart belə
        deyir - şübhə istifadəçinin xeyrinə həll olunur, sayt sahibinin yox).
        """
        if self.disallow_all:
            return False
        if self.allow_all:
            return True

        parts = urlparse.urlparse(url_or_path)
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"

        best: Rule | None = None
        for regex, rule in self._compiled:
            if not regex.match(path):
                continue
            if (
                best is None
                or rule.specificity > best.specificity
                or (rule.specificity == best.specificity and rule.allow)
            ):
                best = rule

        return True if best is None else best.allow
