from __future__ import annotations

from typing import Any


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def extract_stores(payload: Any) -> list[tuple[int, str]]:
    """Best-effort normalization for nearby-store responses."""
    found: list[tuple[int, str]] = []
    seen: set[int] = set()

    for item in _walk(payload):
        if not isinstance(item, dict):
            continue
        raw_id = item.get("storeId") or item.get("id") or item.get("branchId")
        name = item.get("storeName") or item.get("name") or item.get("branchName")
        if raw_id is None or not name:
            continue
        try:
            store_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if store_id not in seen:
            seen.add(store_id)
            found.append((store_id, str(name)))
    return found
