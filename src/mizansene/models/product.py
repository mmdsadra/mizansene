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


@dataclass(slots=True)
class Product:
    id: str
    name: str
    url: str | None = None
    image_url: str | None = None
    price: int | None = None
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

        price = raw.get("price") or raw.get("sellingPrice") or raw.get("discountedPrice")
        try:
            price = int(float(price)) if price is not None else None
        except (TypeError, ValueError):
            price = None

        product_id_text = str(product_id or name)
        raw_url = raw.get("url") or raw.get("productUrl") or raw.get("link")
        url = _normalize_product_url(raw_url, product_id_text, store_id)

        return cls(
            id=product_id_text,
            name=str(name),
            url=url,
            image_url=image,
            price=price,
            available=raw.get("available") if "available" in raw else raw.get("isAvailable"),
            store_id=store_id,
        )
