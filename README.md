# Mizansene

**Mizansene** is a local-first desktop food shopping assistant for Okala.

Type a food, ingredient, or recipe name. Mizansene discovers nearby Okala stores from
coordinates entered in the GUI, lets you select the exact store, searches quantity-filtered
inventory, ranks matching products, keeps local history, and gives a store-specific Okala link.

## Features

- PySide6 desktop GUI
- Collapsible location map with click-to-select, pan and zoom
- Nearby Okala store discovery + explicit store selection
- Fast smart-category search
- Progressive lazy loading of additional categories
- Quantity-filtered store inventory search
- Product price, original price and discount percentage
- Store-specific Okala product URLs
- Editable local recipe notebook
- Fast Yummy Gastronomy YouTube channel index importer
- Optional full YouTube metadata import with local browser cookies
- Recipe completeness checker + ingredient shopping suggestions
- Persian / English / German UI
- Search-history deletion
- SQLite product/search/recipe history
- Persian/English input
- Unit tests + GitHub Actions

## Setup

```bash
git clone https://github.com/mmdsadra/mizansene.git
cd mizansene
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
mizansene
```

Optional environment variable:

```bash
export OKALA_TOKEN='your-current-token'
```

You do **not** need to export latitude, longitude, or a store ID. Open Mizansene,
enter your latitude and longitude, click **Save**, then click **Find nearby stores**.

The search starts with a small category set. **Load more categories** fetches the next
set only when needed, avoiding a nine-request wait for every search.

## Recipe notebook

The **Recipe notebook** button opens an editable local cookbook. Recipes can be created,
edited, deleted, opened at their source URL, and imported from the Yummy Gastronomy
YouTube channel.

The default importer stores the channel index quickly and does not make one network
request per video. YouTube may require authentication for individual video metadata.
For full metadata, set `YOUTUBE_COOKIES_FROM_BROWSER` to a browser name such as
`chrome` or `firefox`, then use **Full metadata**. The app never uploads those
cookies; yt-dlp reads them locally.

The notebook also has a recipe checker and a shopping assistant. It extracts ingredient
lines, flags missing quantities/instructions, builds a checklist, and can send a selected
ingredient directly to the Okala search.

## Architecture

```
GUI
 ├── SearchWorker ── OkalaClient ── Okala gateway
 ├── RecipeDialog ── SQLite recipe notebook
 └── ProductStore ── SQLite products/search history
```

Okala-specific URLs live only in `crawler/client.py`.

## Responsible crawling

Mizansene caches responses and throttles requests. It does not attempt to bypass
authentication, rate limits, CAPTCHAs, or other access controls. Use it in accordance
with Okala's and YouTube's terms and applicable law.

## License

MIT — see [LICENSE](LICENSE).
