# Mizansene

**Mizansene** is a local-first desktop food shopping assistant for Okala.

Type a food, ingredient, or recipe name. Mizansene searches Okala food categories,
ranks matching products, keeps local search/product history, and gives you a direct
Okala link.

## MVP

- PySide6 desktop GUI
- Okala gateway client
- Request throttling + JSON cache
- SQLite product/search history
- Persian/English input
- Product image + price + Okala link
- Search across major food categories when a store ID is supplied
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

Environment variables:

```bash
export OKALA_TOKEN='your-current-token'
export OKALA_STORE_ID='1234'
export OKALA_LAT='YOUR_LATITUDE'
export OKALA_LON='YOUR_LONGITUDE'
```

Do not leave the location unset if you want nearby-store discovery. Mizansene deliberately
does not use a Tehran fallback: it uses the coordinates you provide, then asks Okala for
nearby stores and sorts stores by the distance reported by the API.

For reliable inventory results, select a discovered nearby store (or enter a known store ID)
before searching. Search results are filtered for explicit out-of-stock signals and only
products with a positive textual match are returned; unrelated catalog entries are not used
to fill the result list.

## Architecture

```
GUI
 └── SearchWorker
      ├── OkalaClient ── Okala gateway
      ├── product normalization/ranking
      └── ProductStore ── SQLite
```

Okala-specific URLs live only in `crawler/client.py`, making API changes isolated.

## Roadmap

1. Automatic nearby-store discovery + store picker
2. Inventory indexing into SQLite
3. Recipe → ingredient extraction
4. Quantity/unit normalization
5. Persian fuzzy matching + synonyms
6. Async image caching
7. Shopping lists/favorites/price comparison
8. Linux/Windows releases

## Responsible crawling

Mizansene caches responses and throttles requests. It does not attempt to bypass
authentication, rate limits, CAPTCHAs, or other access controls. Use it in accordance
with Okala's terms and applicable law.

## License

MIT — see [LICENSE](LICENSE).
