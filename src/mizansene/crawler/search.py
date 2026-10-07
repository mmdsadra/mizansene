from __future__ import annotations

from typing import Any

from mizansene.models import Product


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _availability_value(item: dict[str, Any]) -> bool | None:
    for key in (
        "available", "isAvailable", "isAvailableForSale", "isSaleable",
        "saleable", "inStock", "isInStock", "hasQuantity",
    ):
        if key not in item:
            continue
        value = item[key]
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value > 0
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "1", "yes", "available", "in stock", "instock"}:
                return True
            if normalized in {"false", "0", "no", "unavailable", "out of stock", "outofstock"}:
                return False

    for key in ("quantity", "availableQuantity", "stock", "inventory"):
        if key not in item:
            continue
        value = item[key]
        if isinstance(value, (int, float)):
            return value > 0
        if isinstance(value, str):
            try:
                return float(value.replace(",", "")) > 0
            except ValueError:
                pass

    for key in ("isOutOfStock", "outOfStock"):
        if key not in item:
            continue
        value = item[key]
        if isinstance(value, bool):
            return not value
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "1", "yes"}:
                return False
            if normalized in {"false", "0", "no"}:
                return True

    return None


def extract_products(
    payload: Any,
    store_id: int | None = None,
    *,
    available_only: bool = True,
) -> list[Product]:
    products: list[Product] = []
    seen: set[str] = set()

    for item in _walk(payload):
        if not isinstance(item, dict):
            continue
        productish = (
            ("id" in item or "productId" in item or "masterProductId" in item)
            and ("name" in item or "title" in item or "productName" in item)
        )
        if not productish:
            continue

        availability = _availability_value(item)
        if available_only and availability is False:
            continue

        product = Product.from_okala(item, store_id=store_id)
        product.available = availability
        if product.id in seen:
            continue
        seen.add(product.id)
        products.append(product)
    return products


def _normalize_persian(text: str) -> str:
    return (
        text.casefold()
        .replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
    )


def rank_products(products: list[Product], query: str) -> list[Product]:
    terms = [_normalize_persian(part) for part in query.split() if part.strip()]
    normalized_query = " ".join(terms)

    def score(product: Product) -> tuple[int, int]:
        name = _normalize_persian(product.name)
        exact = 10 if normalized_query and normalized_query in name else 0
        words = sum(2 for term in terms if term in name)
        return exact + words, -len(name)

    ranked = [(score(product), product) for product in products]
    ranked = [item for item in ranked if item[0][0] > 0]
    return [product for _, product in sorted(ranked, key=lambda item: item[0], reverse=True)]
