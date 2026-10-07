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
    """Normalize product dictionaries from changing Okala response shapes."""
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
        product = Product.from_okala(item, store_id=store_id)
        if product.id in seen:
            continue
        seen.add(product.id)
        products.append(product)
    return products


def rank_products(products: list[Product], query: str) -> list[Product]:
    terms = [part.casefold() for part in query.split() if part.strip()]
    normalized_query = " ".join(terms)

    def score(product: Product) -> tuple[int, int]:
        name = product.name.casefold()
        exact = 10 if normalized_query and normalized_query in name else 0
        words = sum(2 for term in terms if term in name)
        return exact + words, -len(name)

    return sorted(products, key=score, reverse=True)
