from dataclasses import dataclass
from typing import Any


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

        url = raw.get("url") or raw.get("productUrl") or raw.get("link")
        if not url and product_id is not None:
            url = f"https://www.okala.com/product/{product_id}"

        return cls(
            id=str(product_id or name),
            name=str(name),
            url=url,
            image_url=image,
            price=price,
            available=raw.get("available") if "available" in raw else raw.get("isAvailable"),
            store_id=store_id,
        )
