from __future__ import annotations

import os
from collections.abc import Callable

YUMMY_GASTRONOMY_URL = "https://www.youtube.com/c/YummyGastronomy"

# Offline starter data. Imported YouTube recipes are stored separately in SQLite.
RECIPES: dict[str, list[str]] = {
    "عدس پلو": ["عدس", "برنج", "پیاز", "کشمش", "روغن"],
    "استانبولی": ["برنج", "گوجه", "سیب زمینی", "پیاز", "رب گوجه", "روغن"],
    "قیمه": ["گوشت", "لپه", "پیاز", "رب گوجه", "لیمو عمانی", "برنج", "روغن"],
    "قرمه سبزی": ["سبزی قورمه", "گوشت", "لوبیا قرمز", "پیاز", "لیمو عمانی", "روغن"],
    "قورمه سبزی": ["سبزی قورمه", "گوشت", "لوبیا قرمز", "پیاز", "لیمو عمانی", "برنج", "روغن"],
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


def _description_sections(description: str) -> tuple[str, str]:
    """Best-effort split; keep the original description in instructions."""
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    if not lines:
        return "", ""

    ingredient_markers = ("ingredients", "مواد لازم", "مواد اولیه")
    instruction_markers = ("instructions", "directions", "طرز تهیه", "روش تهیه")
    ingredient_start = next(
        (
            i
            for i, line in enumerate(lines)
            if any(m in line.casefold() for m in ingredient_markers)
        ),
        None,
    )
    instruction_start = next(
        (
            i
            for i, line in enumerate(lines)
            if any(m in line.casefold() for m in instruction_markers)
        ),
        None,
    )
    if ingredient_start is None:
        return "", "\n".join(lines)
    end = (
        instruction_start
        if instruction_start and instruction_start > ingredient_start
        else len(lines)
    )
    ingredients = "\n".join(lines[ingredient_start + 1 : end])
    instructions = "\n".join(
        lines[instruction_start + 1 :] if instruction_start is not None else lines
    )
    return ingredients, instructions


def import_yummy_gastronomy(
    save_recipe: Callable[..., int],
    progress: Callable[[str], None] | None = None,
    *,
    full_metadata: bool = False,
    limit: int | None = None,
    existing_urls: set[str] | None = None,
) -> int:
    """Import the channel index without downloading videos."""
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise RuntimeError("Install yt-dlp to import YouTube recipes.") from exc

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": not full_metadata,
        "ignoreerrors": True,
    }
    browser = os.getenv("YOUTUBE_COOKIES_FROM_BROWSER", "").strip()
    if browser:
        options["cookiesfrombrowser"] = (browser,)
    imported = 0
    with YoutubeDL(options) as ydl:
        channel = ydl.extract_info(YUMMY_GASTRONOMY_URL, download=False)
        entries = [entry for entry in (channel or {}).get("entries") or [] if entry]
        if limit:
            entries = entries[:limit]
        total = len(entries)
        for index, entry in enumerate(entries, 1):
            video_id = entry.get("id")
            title = (entry.get("title") or "").strip()
            if not video_id or not title:
                continue
            url = f"https://www.youtube.com/watch?v={video_id}"
            if existing_urls is not None and url in existing_urls:
                continue
            if progress:
                progress(f"Indexing {index}/{total}: {title}")

            description = (entry.get("description") or "").strip()
            if full_metadata and not description:
                try:
                    details = ydl.extract_info(url, download=False)
                except (DownloadError, OSError, RuntimeError):
                    details = None
                description = ((details or {}).get("description") or "").strip()

            ingredients, instructions = _description_sections(description)
            if not ingredients and not instructions:
                continue
            save_recipe(
                name=title,
                ingredients=ingredients,
                instructions=instructions or description,
                source_url=url,
                source_title=title,
            )
            imported += 1
            if existing_urls is not None:
                existing_urls.add(url)
    return imported
