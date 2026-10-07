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

Optional environment variables:

```bash
export OKALA_TOKEN='your-current-token'
export OKALA_STORE_ID='1234'
export OKALA_LAT='35.805851'
export OKALA_LON='51.431311'
```

The first MVP accepts a store ID in the GUI because Okala's internal store/category
API is more stable when a concrete store is selected. The next iteration will discover
nearby stores automatically and let you choose one.

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
