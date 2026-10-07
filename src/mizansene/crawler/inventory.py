from __future__ import annotations

from dataclasses import dataclass
import httpx


@dataclass(slots=True)
class InventoryItem:
    id: int
    name: str
    quantity_grams: float
    image_url: str | None = None


def find_food_image(name: str) -> str | None:
    """Find a representative food image through Wikimedia Commons."""
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{name} food",
        "gsrnamespace": 6,
        "gsrlimit": 5,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 240,
        "format": "json",
        "origin": "*",
    }
    try:
        response = httpx.get(
            url,
            params=params,
            timeout=8.0,
            headers={"User-Agent": "Mizansene/0.1"},
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
    except (httpx.HTTPError, ValueError):
        return None
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        thumb = info.get("thumburl")
        original = info.get("url")
        if thumb or original:
            return thumb or original
    return None
