# Mizansene

**Mizansene** is a local-first desktop food shopping assistant for Okala.

Type a food, ingredient, or recipe name. Mizansene discovers nearby Okala stores from
coordinates entered in the GUI, lets you select the exact store, searches its
quantity-filtered inventory, ranks matching products, keeps local search/product history,
and gives you a direct Okala link.

## MVP

- PySide6 desktop GUI
- GUI location panel with persistent latitude/longitude
- Nearby Okala store discovery + explicit store selection
- Quantity-filtered store inventory search
- Okala gateway client
- Request throttling + JSON cache
- SQLite product/search history
- Persian/English input
- Product image + price + Okala link
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
enter your latitude and longitude in the **Location** panel, click **Save location**,
then click **Find nearby stores**. The closest returned store is selected automatically,
and you can change the selection before searching.

Search uses Okala's quantity-filtered store search rather than treating a generic catalog
response as in-stock inventory. Products with explicit out-of-stock signals are also
discarded.

## Architecture

```
GUI
 └── SearchWorker
      ├── OkalaClient ── Okala gateway
      ├── quantity-filtered store inventory
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
