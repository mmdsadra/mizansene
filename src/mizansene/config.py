from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("MIZANSENE_DATA_DIR", APP_DIR / "data"))
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "mizansene.sqlite3"

OKALA_TOKEN = os.getenv("OKALA_TOKEN")
OKALA_LAT = float(os.getenv("OKALA_LAT", "35.805851"))
OKALA_LON = float(os.getenv("OKALA_LON", "51.431311"))
OKALA_STORE_ID = os.getenv("OKALA_STORE_ID")
