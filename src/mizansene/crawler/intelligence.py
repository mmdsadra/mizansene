from __future__ import annotations

import re
from dataclasses import dataclass

def _normalize_persian(text: str) -> str:
    return text.casefold().replace("ي", "ی").replace("ى", "ی").replace("ك", "ک").replace("ـ", "").replace("\u200c", " ")


@dataclass(slots=True)
class ParsedIngredient:
    raw: str
    name: str
    quantity: float | None
    unit: str | None


_NUMBER = r"(\d+(?:[.,]\d+)?)"
_UNITS = {
    "گرم": "g",
    "g": "g",
    "کیلو": "kg",
    "کیلوگرم": "kg",
    "kg": "kg",
    "میلی لیتر": "ml",
    "میلی‌لیتر": "ml",
    "ml": "ml",
    "لیتر": "l",
    "l": "l",
    "قاشق": "tbsp",
    "قاشق غذاخوری": "tbsp",
    "قاشق چایخوری": "tsp",
    "عدد": "piece",
    "حبه": "piece",
    "دسته": "bunch",
    "پیمانه": "cup",
}


def _parse_number(value: str) -> float:
    return float(value.replace(",", ".").replace("٫", "."))


def parse_ingredient(line: str) -> ParsedIngredient:
    raw = " ".join(line.strip().split())
    normalized = _normalize_persian(raw)
    quantity = None
    unit = None
    match = re.search(
        rf"(?P<number>{_NUMBER})\\s*(?P<unit>کیلوگرم|کیلو|گرم|میلی ?لیتر|لیتر|"
        rf"قاشق(?: غذاخوری| چایخوری)?|پیمانه|عدد|حبه|دسته|kg|g|ml|l)\\b?",
        normalized,
        re.IGNORECASE,
    )
    if match:
        quantity = _parse_number(match.group("number"))
        unit = _UNITS.get(match.group("unit").strip().casefold())
        name = (normalized[: match.start()] + " " + normalized[match.end() :]).strip()
    else:
        piece = re.match(rf"^({_NUMBER})\\s+(.+)$", normalized)
        if piece:
            quantity = _parse_number(piece.group(1))
            unit = "piece"
            name = piece.group(2).strip()
        else:
            name = normalized
    name = re.sub(r"^[\-–—•*]+\\s*", "", name).strip(" :،,")
    return ParsedIngredient(raw=raw, name=name, quantity=quantity, unit=unit)


def analyze_recipe(ingredients_text: str) -> list[ParsedIngredient]:
    return [
        parse_ingredient(line)
        for line in ingredients_text.splitlines()
        if line.strip()
    ]


def quantity_in_grams(item: ParsedIngredient) -> float | None:
    if item.quantity is None:
        return None
    if item.unit == "g":
        return item.quantity
    if item.unit == "kg":
        return item.quantity * 1000
    return None


def shopping_gap(recipe_items: list[ParsedIngredient], inventory: dict[str, float]) -> list[dict]:
    gaps = []
    for item in recipe_items:
        required = quantity_in_grams(item)
        if required is None:
            gaps.append({"ingredient": item.name, "required": None, "available": None})
            continue
        available = inventory.get(item.name, 0.0)
        gaps.append(
            {
                "ingredient": item.name,
                "required": required,
                "available": available,
                "missing": max(0.0, required - available),
            }
        )
    return gaps
