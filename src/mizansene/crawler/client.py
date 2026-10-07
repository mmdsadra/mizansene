from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx


class OkalaError(RuntimeError):
    pass


class OkalaClient:
    """Rate-limited, cached client for the Okala gateway.

    Keeping all Okala-specific URLs here means the GUI and database don't
    need to know anything about Okala's internal API.
    """

    BASE_URL = "https://apigateway.okala.com"

    def __init__(self, token: str | None = None, cache_dir: Path | None = None,
                 timeout: float = 20.0, request_delay: float = 0.7) -> None:
        self.token = token
        self.cache_dir = cache_dir
        self.request_delay = request_delay
        self._last_request = 0.0
        self.http = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"Accept": "application/json",
                     "User-Agent": "Mizansene/0.1 (+local food shopping assistant)"},
        )
        if token:
            self.http.headers["Authorization"] = f"Bearer {token}"

    def close(self) -> None:
        self.http.close()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(
            json.dumps([path, params], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        cache_file = self.cache_dir / f"{key}.json" if self.cache_dir else None
        if cache_file and cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cache_file.unlink(missing_ok=True)

        wait = self.request_delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)

        try:
            response = self.http.get(f"{self.BASE_URL}{path}", params=params)
            self._last_request = time.monotonic()
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise OkalaError(
                    "Okala rejected the request. Set a current OKALA_TOKEN if this endpoint requires authentication."
                ) from exc
            if exc.response.status_code == 429:
                raise OkalaError("Okala rate-limited the request; wait and try again.") from exc
            raise OkalaError(f"Okala returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise OkalaError(f"Could not connect to Okala: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise OkalaError("Okala returned a non-JSON response.") from exc

        if cache_file:
            cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def nearby(self, slug: str, lat: float, lon: float) -> Any:
        return self._get("/api/unicorn/v2/products/nearby",
                         {"slug": slug, "lat": lat, "lon": lon})

    def store_category(self, store_id: int, slug: str, category_id: int) -> Any:
        return self._get(f"/api/unicorn/v2/products/store/{store_id}",
                         {"pC_Id": category_id, "slug": slug})

    def product_detail(self, store_id: int, product_id: int) -> Any:
        return self._get("/api/Unicorn/v1/catalog/pdp",
                         {"sId": store_id, "pId": product_id})
