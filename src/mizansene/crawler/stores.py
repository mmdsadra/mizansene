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


def _distance(item: dict[str, Any]) -> float | None:
    for key in ("distance", "distanceKm", "distanceInKm", "distanceKM"):
        value = item.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def extract_stores(payload: Any) -> list[tuple[int, str]]:
    """Extract actual store records and sort by reported distance."""
    found: list[tuple[int, str, float | None]] = []
    seen: set[int] = set()

    for item in _walk(payload):
        if not isinstance(item, dict):
            continue

        raw_id = item.get("storeId") or item.get("branchId")
        name = item.get("storeName") or item.get("branchName") or item.get("storeTitle")
        if raw_id is None or not name:
            continue

        try:
            store_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        if store_id in seen:
            continue
        seen.add(store_id)
        found.append((store_id, str(name), _distance(item)))

    found.sort(key=lambda entry: (
        entry[2] is None,
        entry[2] if entry[2] is not None else float("inf"),
    ))
    return [(store_id, name) for store_id, name, _ in found]
