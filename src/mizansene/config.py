from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("MIZANSENE_DATA_DIR", APP_DIR / "data"))
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "mizansene.sqlite3"

OKALA_TOKEN = os.getenv("OKALA_TOKEN")
OKALA_STORE_ID = os.getenv("OKALA_STORE_ID")


def _optional_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid decimal latitude/longitude.") from exc


# Never silently default to Tehran. Nearby-store discovery requires explicit
# coordinates supplied by the user/environment.
OKALA_LAT = _optional_float("OKALA_LAT")
OKALA_LON = _optional_float("OKALA_LON")

if (OKALA_LAT is None) != (OKALA_LON is None):
    raise ValueError("Set both OKALA_LAT and OKALA_LON, or leave both unset.")
