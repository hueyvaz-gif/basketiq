"""
Əmri icra edir və insan dilində cavab qaytarır.

Bu qat ÖZ MƏNTİQİNİ YAZMIR - `app/api/*` funksiyalarını çağırır, eynilə MCP
serveri kimi. Səbəb: səbət qaydaları ("natamam market qalib elan edilmir")
bir yerdə qalmalıdır. İndi eyni məntiqin ÜÇ qapısı var - HTTP, MCP, səs -
və üçü də eyni koda gedir.

CAVABLAR QISADIR. Telegram mesajı ekranda oxunur; 20 sətirlik cədvəl orada
faydasızdır. Ona görə hər cavab 2-5 sətirdir.
"""

from app.api import basket, products
from app.api.basket import BasketItemIn
from app.profile import get_profile
from app.recommend import recommend
from voice.commands import Command


def _search(query: str, limit: int = 5) -> list[dict]:
    """
    Məhsul axtarışı, geri çəkilmə ilə.

    Niyə? Səs mətnində əmr sözü qala bilər: "düyü satılır". Tam sorğu heç nə
    tapmasa, sözləri BİR-BİR yoxlayırıq və nəticə verən ilkini götürürük.

    Niyə "ən uzun söz" deyil? Ölçüldü: zibil söz məhsulun adından uzun ola
    bilər ("tapilmayansoz" 13 hərf, "düyü" 4). Uzunluq sözün faydalı olduğunu
    göstərmir - yalnız axtarışın nəticəsi göstərir. Uzunluq sadəcə YOXLAMA
    SIRASINI müəyyən edir, çünki uzun söz daha spesifikdir.
    """
    query = (query or "").strip()
    if not query:
        return []

    items = products.search_products(q=query, limit=limit)["items"]
    if items or " " not in query:
        return items

    for word in sorted(query.split(), key=len, reverse=True):
        if len(word) < 3:
            continue
        items = products.search_products(q=word, limit=limit)["items"]
        if items:
            return items
    return []


def _describe(item: dict) -> str:
    parts = [item["name"]]
    if item.get("brand"):
        parts.insert(0, item["brand"])
    if item.get("size_value") and item.get("size_unit"):
        value = item["size_value"]
        number = int(value) if float(value).is_integer() else value
        parts.append(f"{number} {item['size_unit']}")
    return " ".join(str(p) for p in parts)


def run(command: Command) -> str:
    if command.intent == "unknown":
        return (
            "Başa düşmədim. Nümunə əmrlər:\n"
            "• «səbətə iki litr süd əlavə et»\n"
            "• «səbətim harada ucuzdur»\n"
            "• «düyü neçəyədir»\n"
            "• «səbətimdə nə var»"
        )

    if command.intent == "show":
        items = basket.get_basket()["items"]
        if not items:
            return "Səbət boşdur."
        lines = [f"Səbətdə {len(items)} məhsul:"]
        lines += [f"• {row['name']} ×{row['qty']:g}" for row in items]
        return "\n".join(lines)

    if command.intent == "compare":
        data = basket.compare()
        if not data["items"]:
            return "Səbət boşdur - əvvəlcə məhsul əlavə et."

        rec = recommend(data, get_profile()).as_dict()
        if rec["plan"] == "yoxdur":
            return "\n".join(rec["notes"]) or "Müqayisə mümkün olmadı."

        plan = "bölünmüş alış" if rec["plan"] == "bolunmus" else "tək market"
        lines = [f"{plan}: {', '.join(rec['stores'])} — {rec['total']:.2f} AZN"]
        lines += [f"• {note}" for note in rec["notes"][:2]]
        lines += [f"⚠ {warn}" for warn in rec["warnings"][:2]]
        return "\n".join(lines)

    if command.intent == "price":
        items = _search(command.query)
        if not items:
            return f"«{command.query}» tapılmadı."
        lines = [f"«{command.query}» üzrə {len(items)} nəticə:"]
        for item in items:
            lines.append(f"• {_describe(item)} — {item['store_count']} marketdə")
        lines.append("Səbətə əlavə etmək üçün: «səbətə " + items[0]["name"] + " əlavə et»")
        return "\n".join(lines)

    if command.intent == "add":
        items = _search(command.query, limit=3)
        if not items:
            return f"«{command.query}» tapılmadı - səbətə əlavə edə bilmədim."
        # Ən çox marketdə olan məhsul seçilir: müqayisə üçün ən faydalısı odur
        chosen = items[0]
        basket.add_item(BasketItemIn(product_id=chosen["id"], qty=command.qty))
        reply = f"Səbətə əlavə olundu: {_describe(chosen)} ×{command.qty:g}"
        if len(items) > 1:
            others = ", ".join(_describe(i) for i in items[1:])
            reply += f"\n(başqa uyğunlar da var: {others})"
        return reply

    if command.intent == "remove":
        current = basket.get_basket()["items"]
        query = command.query.lower()
        match = next(
            (row for row in current if query in row["name"].lower()
             or query.rstrip("üniı") in row["name"].lower()),
            None,
        )
        if match is None:
            return f"Səbətdə «{command.query}» tapılmadı."
        basket.remove_item(match["product_id"])
        return f"Səbətdən çıxarıldı: {match['name']}"

    return "Bu əmr hələ dəstəklənmir."
