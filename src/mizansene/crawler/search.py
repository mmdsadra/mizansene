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


def extract_products(payload: Any, store_id: int | None = None) -> list[Product]:
    """Normalize products from Okala responses without depending on one exact schema."""
    products: list[Product] = []
    seen: set[str] = set()

    for item in _walk(payload):
        if not isinstance(item, dict):
            continue
        if not any(k in item for k in ("productId", "masterProductId", "productName", "sellingPrice")):
            continue
        product = Product.from_okala(item, store_id=store_id)
        if product.id in seen:
            continue
        seen.add(product.id)
        products.append(product)
    return products


def rank_products(products: list[Product], query: str) -> list[Product]:
    terms = [part.casefold() for part in query.split() if part.strip()]

    def score(product: Product) -> tuple[int, int]:
        name = product.name.casefold()
        exact = 3 if query.casefold() in name else 0
        words = sum(1 for term in terms if term in name)
        return exact + words, -len(name)

    return sorted(products, key=score, reverse=True)
