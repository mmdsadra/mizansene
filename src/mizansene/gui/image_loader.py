from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from PySide6.QtCore import QThread, Signal


class ImageLoadWorker(QThread):
    image_ready = Signal(str, bytes)
    failed = Signal(str)

    def __init__(self, items: list[tuple[str, str]], cache_dir: Path):
        super().__init__()
        self.items = items
        self.cache_dir = cache_dir

    def run(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        def fetch(item):
            key, url = item
            cache = self.cache_dir / f"image-{hashlib.sha256(url.encode()).hexdigest()}.bin"
            if cache.exists():
                try:
                    return key, cache.read_bytes()
                except OSError:
                    pass
            try:
                response = httpx.get(
                    url,
                    timeout=5.0,
                    follow_redirects=True,
                    headers={"User-Agent": "Mizansene/0.1"},
                )
                response.raise_for_status()
                data = response.content
                try:
                    cache.write_bytes(data)
                except OSError:
                    pass
                return key, data
            except httpx.HTTPError:
                return key, b""

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch, item) for item in self.items]
            for future in as_completed(futures):
                if self.isInterruptionRequested():
                    return
                key, data = future.result()
                if data:
                    self.image_ready.emit(key, data)
