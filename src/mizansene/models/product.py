from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


def _store_product_url(product_id: str, store_id: int | None) -> str:
    if store_id is None:
        return f"https://www.okala.com/product/{product_id}"
    return f"https://www.okala.com/store/{store_id}/product/{product_id}"


def _normalize_product_url(url: str | None, product_id: str, store_id: int | None) -> str:
    fallback = _store_product_url(product_id, store_id)
    if not url:
        return fallback
    try:
        parsed = urlsplit(str(url))
        if parsed.netloc.endswith("okala.com") and parsed.path.rstrip("/").startswith("/product/"):
            return fallback
    except ValueError:
        return fallback
    return str(url)


def _first_number(raw: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = raw.get(key)
        if value is None:
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return None


@dataclass(slots=True)
class Product:
    id: str
    name: str
    url: str | None = None
    image_url: str | None = None
    price: int | None = None
    original_price: int | None = None
    discount_percent: float | None = None
    available: bool | None = None
    store_id: int | None = None

    @classmethod
    def from_okala(cls, raw: dict[str, Any], store_id: int | None = None) -> "Product":
        product_id = raw.get("id") or raw.get("productId") or raw.get("masterProductId")
        name = raw.get("name") or raw.get("title") or raw.get("productName") or "Unnamed product"

        image = (
            raw.get("imageUrl")
            or raw.get("image")
            or raw.get("imageURL")
            or raw.get("productImage")
        )
        if isinstance(image, dict):
            image = image.get("url") or image.get("src")

        price = _first_number(
            raw,
            ("price", "sellingPrice", "discountedPrice", "discountPrice", "finalPrice"),
        )
        original_price = _first_number(
            raw,
            ("originalPrice", "priceBeforeDiscount", "basePrice", "listPrice", "oldPrice"),
        )
        discount = raw.get("discountPercent") or raw.get("discountPercentage") or raw.get("discount")
        try:
            discount = float(discount) if discount is not None else None
        except (TypeError, ValueError):
            discount = None

        if original_price and price and original_price > price and not discount:
            discount = round((original_price - price) * 100 / original_price, 1)

        product_id_text = str(product_id or name)
        raw_url = raw.get("url") or raw.get("productUrl") or raw.get("link")

        return cls(
            id=product_id_text,
            name=str(name),
            url=_normalize_product_url(raw_url, product_id_text, store_id),
            image_url=image,
            price=price,
            original_price=original_price,
            discount_percent=discount,
            available=raw.get("available") if "available" in raw else raw.get("isAvailable"),
            store_id=store_id,
        )
