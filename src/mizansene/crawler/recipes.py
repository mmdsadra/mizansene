from __future__ import annotations

# Small offline starter dictionary. This is deliberately data, not application
# logic, so it can grow without changing the crawler.
RECIPES: dict[str, list[str]] = {
    "عدس پلو": ["عدس", "برنج", "پیاز", "کشمش", "روغن"],
    "استانبولی": ["برنج", "گوجه", "سیب زمینی", "پیاز", "رب گوجه", "روغن"],
    "قیمه": ["گوشت", "لپه", "پیاز", "رب گوجه", "لیمو عمانی", "برنج", "روغن"],
    "قرمه سبزی": ["سبزی قورمه", "گوشت", "لوبیا قرمز", "پیاز", "لیمو عمانی", "روغن"],
    "قورمه سبزی": ["سبزی قورمه", "گوشت", "لوبیا قرمز", "پیاز", "لیمو عمانی", "روغن"],
    "آبگوشت": ["گوشت", "نخود", "لوبیا سفید", "سیب زمینی", "گوجه", "پیاز"],
    "ماکارونی": ["ماکارونی", "گوشت چرخ کرده", "پیاز", "رب گوجه", "روغن"],
    "کتلت": ["گوشت چرخ کرده", "سیب زمینی", "پیاز", "تخم مرغ", "آرد", "روغن"],
}


def ingredients_for(query: str) -> list[str] | None:
    normalized = " ".join(query.casefold().split())
    for recipe, ingredients in RECIPES.items():
        if recipe.casefold() == normalized:
            return ingredients
    return None
