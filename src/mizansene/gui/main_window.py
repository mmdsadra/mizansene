from __future__ import annotations

import webbrowser

import httpx
from PySide6.QtCore import QObject, QSettings, Qt, QThread, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mizansene.config import CACHE_DIR, DB_PATH, OKALA_TOKEN
from mizansene.crawler.client import OkalaClient, OkalaError
from mizansene.crawler.recipes import ingredients_for
from mizansene.crawler.search import extract_products, rank_products
from mizansene.crawler.stores import extract_stores
from mizansene.database.store import ProductStore

FOOD_CATEGORIES = [
    ("groceries", 1461),
    ("dairy-products", 1462),
    ("proteins", 1463),
    ("canned-ready-food", 1464),
    ("beverages", 1465),
    ("breakfast-goods", 1466),
    ("nuts-sweets", 1468),
    ("spices", 1469),
    ("fruits-vegetables", 1470),
]


class SearchWorker(QThread):
    batch = Signal(list)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, query: str, store_id: int | None):
        super().__init__()
        self.query = query
        self.store_id = store_id

    def _rank(self, products):
        ingredients = ingredients_for(self.query)
        terms = ingredients or [self.query]
        if ingredients:
            ranked: list[tuple[int, object]] = []
            for product in products:
                name = product.name.casefold()
                score = sum(
                    1
                    for ingredient in terms
                    if ingredient.casefold() in name
                )
                if score:
                    ranked.append((score, product))
            return [
                product
                for _, product in sorted(
                    ranked,
                    key=lambda pair: (pair[0], -len(pair[1].name)),
                    reverse=True,
                )
            ]
        return rank_products(products, self.query)

    def run(self):
        if not self.store_id:
            self.failed.emit("Select an Okala store before searching.")
            return

        products_by_id = {}
        try:
            # Three requests at a time keeps the UI responsive while avoiding
            # the long 9-category serial wait. Each completed category is
            # emitted immediately, so results appear progressively.
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def fetch_category(slug):
                client = OkalaClient(
                    token=OKALA_TOKEN,
                    cache_dir=CACHE_DIR,
                    request_delay=0.15,
                )
                try:
                    payload = client.store_category_available(self.store_id, slug)
                    return extract_products(
                        payload,
                        self.store_id,
                        available_only=True,
                        assume_available=True,
                    )
                finally:
                    client.close()

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(fetch_category, slug)
                    for slug, _ in FOOD_CATEGORIES
                ]
                for future in as_completed(futures):
                    for product in future.result():
                        products_by_id.setdefault(product.id, product)
                    ranked = self._rank(list(products_by_id.values()))
                    self.batch.emit(ranked[:60])

            final = self._rank(list(products_by_id.values()))
            self.finished.emit(final[:60])
        except OkalaError as exc:
            self.failed.emit(str(exc))
        except ValueError as exc:
            self.failed.emit(f"Search failed: {exc}")

class StoreWorker(QThread):
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, lat: float, lon: float):
        super().__init__()
        self.lat = lat
        self.lon = lon

    def run(self):
        client = OkalaClient(token=OKALA_TOKEN, cache_dir=CACHE_DIR)
        try:
            payload = client.nearby("groceries", self.lat, self.lon)
            self.finished.emit(extract_stores(payload))
        except OkalaError as exc:
            self.failed.emit(str(exc))
        finally:
            client.close()


class ProductItem(QWidget):
    def __init__(self, product):
        super().__init__()
        layout = QHBoxLayout(self)
        image = QLabel("No image")
        image.setFixedSize(96, 96)
        image.setAlignment(Qt.AlignCenter)
        image.setStyleSheet("border: 1px solid #ddd;")
        if product.image_url:
            response = None
            try:
                response = httpx.get(product.image_url, timeout=8)
                response.raise_for_status()
                pixmap = QPixmap()
                if pixmap.loadFromData(response.content):
                    image.setPixmap(
                        pixmap.scaled(
                            96,
                            96,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        )
                    )
            except httpx.HTTPError:
                pass
        layout.addWidget(image)

        text = QVBoxLayout()
        name = QLabel(product.name)
        name.setWordWrap(True)
        name.setStyleSheet("font-size: 15px; font-weight: 600;")
        text.addWidget(name)
        if product.price is not None:
            text.addWidget(QLabel(f"{product.price:,} تومان"))
        if product.available is True:
            text.addWidget(QLabel("موجود"))
        elif product.available is False:
            text.addWidget(QLabel("ناموجود"))
        if product.url:
            button = QPushButton("Open in Okala")
            button.clicked.connect(lambda: webbrowser.open(product.url))
            text.addWidget(button)
        layout.addLayout(text)



class LocationBridge(QObject):
    def __init__(self, window):
        super().__init__()
        self.window = window

    @Slot(float, float)
    def locationSelected(self, lat: float, lon: float):
        self.window.set_map_location(lat, lon)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mizansene — Okala food finder")
        self.resize(860, 820)
        self.store = ProductStore(DB_PATH)
        self.worker = None
        self.store_worker = None
        self.current_products = {}
        self.settings = QSettings("Mizansene", "Mizansene")

        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("What do you want to cook or buy?")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(title)

        location_box = QGroupBox("Location")
        location_layout = QVBoxLayout(location_box)
        self.latitude = QLineEdit(str(self.settings.value("latitude", "")))
        self.longitude = QLineEdit(str(self.settings.value("longitude", "")))
        self.latitude.setPlaceholderText("Latitude, e.g. 32.6613")
        self.longitude.setPlaceholderText("Longitude, e.g. 51.6804")

        coordinate_row = QHBoxLayout()
        coordinate_row.addWidget(self.latitude)
        coordinate_row.addWidget(self.longitude)
        location_layout.addLayout(coordinate_row)

        self.map = QWebEngineView()
        self.map.setMinimumHeight(280)
        self.map_bridge = LocationBridge(self)
        self.map_channel = QWebChannel(self.map.page())
        self.map_channel.registerObject("bridge", self.map_bridge)
        self.map.page().setWebChannel(self.map_channel)
        self.map.setHtml(self._map_html(), baseUrl="https://localhost/")
        location_layout.addWidget(self.map)

        location_buttons = QHBoxLayout()
        save_location = QPushButton("Save location")
        save_location.clicked.connect(self.save_location)
        location_buttons.addWidget(save_location)
        find_stores = QPushButton("Find nearby stores")
        find_stores.clicked.connect(self.discover_stores)
        location_buttons.addWidget(find_stores)
        location_layout.addLayout(location_buttons)
        layout.addWidget(location_box)

        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("مثلاً: عدس پلو، شیر، مرغ، رب گوجه")
        self.search.returnPressed.connect(self.start_search)
        row.addWidget(self.search)

        self.store_combo = QComboBox()
        self.store_combo.setMinimumWidth(280)
        self.store_combo.addItem("Choose a nearby store", None)
        self.store_combo.currentIndexChanged.connect(self.store_changed)
        row.addWidget(self.store_combo)

        button = QPushButton("Search")
        button.clicked.connect(self.start_search)
        row.addWidget(button)
        layout.addLayout(row)

        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("Manual store ID:"))
        self.manual_store = QLineEdit()
        self.manual_store.setPlaceholderText("Optional")
        manual_row.addWidget(self.manual_store)
        use_manual = QPushButton("Use ID")
        use_manual.clicked.connect(self.use_manual_store)
        manual_row.addWidget(use_manual)
        layout.addLayout(manual_row)

        self.selected_store_label = QLabel("Selected store ID: —")
        layout.addWidget(self.selected_store_label)

        recent = self.store.recent_searches()
        history = QLabel("Recent: " + (" • ".join(recent) if recent else "none"))
        history.setWordWrap(True)
        layout.addWidget(history)

        self.status = QLabel(
            "Enter your location, find nearby stores, select one, then search."
        )
        layout.addWidget(self.status)
        self.results = QListWidget()
        layout.addWidget(self.results)
        self.setCentralWidget(root)

    def _map_html(self) -> str:
        saved_lat = self.settings.value("latitude", 32.5)
        saved_lon = self.settings.value("longitude", 53.7)
        return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>html,body,#map{{height:100%;margin:0}}</style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
new QWebChannel(qt.webChannelTransport, function(channel) {{
    window.bridge = channel.objects.bridge;
    const lat = {float(saved_lat)};
    const lon = {float(saved_lon)};
    const map = L.map('map').setView([lat, lon], 13);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);
    let marker = L.marker([lat, lon]).addTo(map);
    map.on('click', function(e) {{
        marker.setLatLng(e.latlng);
        window.bridge.locationSelected(e.latlng.lat, e.latlng.lng);
    }});
}});
</script>
</body>
</html>
"""

    def set_map_location(self, lat: float, lon: float):
        self.latitude.setText(f"{lat:.6f}")
        self.longitude.setText(f"{lon:.6f}")
        self.settings.setValue("latitude", lat)
        self.settings.setValue("longitude", lon)
        self.status.setText(f"Map location selected: {lat:.6f}, {lon:.6f}")

    def save_location(self):
        try:
            lat = float(self.latitude.text().strip())
            lon = float(self.longitude.text().strip())
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid location",
                "Latitude and longitude must be decimal numbers.",
            )
            return

        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            QMessageBox.warning(
                self,
                "Invalid location",
                "Latitude must be between -90 and 90 and longitude between -180 and 180.",
            )
            return

        self.settings.setValue("latitude", lat)
        self.settings.setValue("longitude", lon)
        self.status.setText("Location saved. You can now find nearby stores.")

    def location_values(self) -> tuple[float, float] | None:
        try:
            lat = float(self.latitude.text().strip())
            lon = float(self.longitude.text().strip())
        except ValueError:
            return None
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            return None
        return lat, lon

    def discover_stores(self):
        location = self.location_values()
        if location is None:
            QMessageBox.warning(
                self,
                "Set location",
                "Enter a valid latitude and longitude first.",
            )
            return

        self.save_location()
        self.status.setText("Finding nearby Okala stores…")
        self.store_combo.clear()
        self.store_combo.addItem("Finding stores…", None)
        self.store_combo.setEnabled(False)
        self.manual_store.clear()
        self.store_worker = StoreWorker(*location)
        self.store_worker.finished.connect(self.show_stores)
        self.store_worker.failed.connect(self.show_error)
        self.store_worker.start()

    def show_stores(self, stores):
        self.store_combo.setEnabled(True)
        self.store_combo.clear()
        self.store_combo.addItem("Choose a nearby store", None)
        for store_id, name in stores:
            self.store_combo.addItem(f"{name} ({store_id})", store_id)

        if stores:
            self.store_combo.setCurrentIndex(1)
            self.status.setText(
                f"Found {len(stores)} nearby stores. Closest store selected; you can change it."
            )
        else:
            self.status.setText("No nearby Okala stores were returned.")

    def store_changed(self, _index: int):
        store_id = self.store_combo.currentData()
        if store_id is None:
            self.selected_store_label.setText("Selected store ID: —")
            return
        self.manual_store.clear()
        self.selected_store_label.setText(f"Selected store ID: {int(store_id)}")

    def use_manual_store(self):
        raw = self.manual_store.text().strip()
        try:
            store_id = int(raw)
        except ValueError:
            QMessageBox.warning(self, "Invalid store ID", "Store ID must be a number.")
            return
        self.store_combo.setCurrentIndex(0)
        self.selected_store_label.setText(f"Selected store ID: {store_id}")
        self.status.setText(f"Using manually entered Okala store {store_id}.")

    def selected_store_id(self) -> int | None:
        combo_value = self.store_combo.currentData()
        if combo_value is not None:
            return int(combo_value)

        raw = self.manual_store.text().strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def start_search(self):
        query = self.search.text().strip()
        if not query:
            return

        store_id = self.selected_store_id()
        if store_id is None:
            QMessageBox.information(
                self,
                "Choose a store",
                "Find nearby stores and select one first, or enter a store ID manually.",
            )
            return

        self.store.add_search(query)
        self.status.setText(f"Searching store {store_id} for available products…")
        self.results.clear()
        self.worker = SearchWorker(query, store_id)
        self.worker.batch.connect(self.show_batch)
        self.worker.finished.connect(self.show_results)
        self.worker.failed.connect(self.show_error)
        self.worker.start()

    def show_batch(self, products):
        self._render_products(products, clear=True)
        self.status.setText(f"Loading… {len(products)} matching products found so far.")

    def show_results(self, products):
        self._render_products(products, clear=True)
        if not products:
            self.status.setText("No matching available products found in this store.")
            return
        self.status.setText(f"Found {len(products)} available matches.")
        self.store.save_products(products)

    def _render_products(self, products, *, clear: bool):
        if clear:
            self.results.clear()
        self.current_products = {product.id: product for product in products}
        for product in products:
            item = QListWidgetItem()
            widget = ProductItem(product)
            item.setSizeHint(widget.sizeHint())
            self.results.addItem(item)
            self.results.setItemWidget(item, widget)

    def show_error(self, message: str):
        self.store_combo.setEnabled(True)
        self.status.setText("Request failed.")
        QMessageBox.warning(self, "Okala error", message)
