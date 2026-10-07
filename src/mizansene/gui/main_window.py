from __future__ import annotations

import math
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QPainter, QPixmap
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
from mizansene.gui.recipe_dialog import RecipeDialog

FOOD_CATEGORIES = [
    ("groceries", 1461, "Groceries"),
    ("dairy-products", 1462, "Dairy"),
    ("proteins", 1463, "Protein"),
    ("canned-ready-food", 1464, "Canned & ready food"),
    ("beverages", 1465, "Beverages"),
    ("breakfast-goods", 1466, "Breakfast"),
    ("nuts-sweets", 1468, "Nuts & sweets"),
    ("spices", 1469, "Spices"),
    ("fruits-vegetables", 1470, "Fruit & vegetables"),
]


def categories_for_query(query: str, selected: str) -> list[tuple[str, int, str]]:
    if selected != "__smart__":
        return [item for item in FOOD_CATEGORIES if item[0] == selected]

    text = query.casefold()
    groups = {
        "dairy-products": ("شیر", "ماست", "پنیر", "خامه", "کره"),
        "proteins": ("مرغ", "گوشت", "ماهی", "تن", "تخم مرغ", "تخم‌مرغ"),
        "canned-ready-food": ("کنسرو", "رب", "ماکارونی", "نودل"),
        "beverages": ("نوشابه", "آب", "آبمیوه", "قهوه", "چای"),
        "breakfast-goods": ("عسل", "مربا", "ارده", "صبحانه"),
        "nuts-sweets": ("آجیل", "شکلات", "بیسکویت", "کیک", "شیرینی"),
        "spices": ("ادویه", "نمک", "فلفل", "زردچوبه"),
        "fruits-vegetables": ("گوجه", "پیاز", "سیب", "سبزی", "میوه", "سیب زمینی"),
    }
    for slug, terms in groups.items():
        if any(term in text for term in terms):
            return [item for item in FOOD_CATEGORIES if item[0] == slug]

    # The first three are a deliberately small, cheap first pass.
    return FOOD_CATEGORIES[:3]


class SearchWorker(QThread):
    batch = Signal(list)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, query: str, store_id: int, categories):
        super().__init__()
        self.query = query
        self.store_id = store_id
        self.categories = categories

    def _rank(self, products):
        ingredients = ingredients_for(self.query)
        terms = ingredients or [self.query]
        if ingredients:
            ranked = []
            for product in products:
                name = product.name.casefold()
                score = sum(1 for ingredient in terms if ingredient.casefold() in name)
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
        products_by_id = {}
        try:
            def fetch_category(slug):
                client = OkalaClient(
                    token=OKALA_TOKEN,
                    cache_dir=CACHE_DIR,
                    request_delay=0.1,
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

            with ThreadPoolExecutor(max_workers=min(3, len(self.categories))) as executor:
                futures = [executor.submit(fetch_category, item[0]) for item in self.categories]
                for future in as_completed(futures):
                    for product in future.result():
                        products_by_id.setdefault(product.id, product)
                    self.batch.emit(self._rank(list(products_by_id.values()))[:30])

            self.finished.emit(self._rank(list(products_by_id.values()))[:30])
        except (OkalaError, ValueError) as exc:
            self.failed.emit(f"Search failed: {exc}")


class StoreWorker(QThread):
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, lat: float, lon: float):
        super().__init__()
        self.lat, self.lon = lat, lon

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
        layout.setContentsMargins(8, 8, 8, 8)

        image = QLabel("Image")
        image.setFixedSize(72, 72)
        image.setAlignment(Qt.AlignCenter)
        image.setStyleSheet("border: 1px solid #ddd; color: #888;")
        layout.addWidget(image)

        text = QVBoxLayout()
        name = QLabel(product.name)
        name.setWordWrap(True)
        name.setStyleSheet("font-size: 14px; font-weight: 600;")
        text.addWidget(name)

        if product.price is not None:
            price_row = QHBoxLayout()
            if (
                product.original_price is not None
                and product.original_price > product.price
            ):
                old = QLabel(f"<s>{product.original_price:,}</s> تومان")
                old.setStyleSheet("color: #888;")
                price_row.addWidget(old)
            current = QLabel(f"{product.price:,} تومان")
            current.setStyleSheet("font-weight: 600;")
            price_row.addWidget(current)
            if product.discount_percent:
                discount = QLabel(f"{product.discount_percent:g}% تخفیف")
                discount.setStyleSheet("font-weight: 700;")
                price_row.addWidget(discount)
            price_row.addStretch()
            text.addLayout(price_row)

        if product.available is True:
            text.addWidget(QLabel("موجود"))
        elif product.available is False:
            text.addWidget(QLabel("ناموجود"))

        if product.url:
            button = QPushButton("Open in Okala")
            button.clicked.connect(lambda: webbrowser.open(product.url))
            text.addWidget(button)
        layout.addLayout(text)


def _latlon_to_world(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    lat = max(-85.05112878, min(85.05112878, lat))
    scale = 2**zoom
    x = (lon + 180.0) / 360.0 * scale
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * scale
    return x, y


def _world_to_latlon(x: float, y: float, zoom: int) -> tuple[float, float]:
    scale = 2**zoom
    lon = x / scale * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * y / scale
    return math.degrees(math.atan(math.sinh(n))), lon


class MapTileWorker(QThread):
    tiles_ready = Signal(object)

    def __init__(self, center_x: float, center_y: float, zoom: int):
        super().__init__()
        self.center_x, self.center_y, self.zoom = center_x, center_y, zoom

    def run(self):
        tiles = {}
        max_tile = 2**self.zoom
        tx0 = math.floor(self.center_x / 256) - 1
        ty0 = math.floor(self.center_y / 256) - 1
        client = httpx.Client(timeout=3, headers={"User-Agent": "Mizansene/0.1"})
        try:
            for tx in range(tx0, tx0 + 3):
                for ty in range(ty0, ty0 + 3):
                    if ty < 0 or ty >= max_tile:
                        continue
                    url = f"https://tile.openstreetmap.org/{self.zoom}/{tx % max_tile}/{ty}.png"
                    try:
                        response = client.get(url)
                        response.raise_for_status()
                    except httpx.HTTPError:
                        continue
                    tiles[(tx, ty)] = response.content
        finally:
            client.close()
        self.tiles_ready.emit(tiles)


class MapWidget(QWidget):
    locationSelected = Signal(float, float)

    def __init__(self, lat: float, lon: float, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.zoom = 13
        self.lat, self.lon = lat, lon
        self.tiles: dict[tuple[int, int], QPixmap] = {}
        self.center_world = _latlon_to_world(lat, lon, self.zoom)
        self.tile_worker: MapTileWorker | None = None
        self.drag_start = None
        self.press_pos = None
        self._load_tiles()

    def _stop_tile_worker(self):
        if self.tile_worker is not None and self.tile_worker.isRunning():
            self.tile_worker.requestInterruption()
            self.tile_worker.wait(3500)
        self.tile_worker = None

    def close(self):
        self._stop_tile_worker()

    def _load_tiles(self):
        self._stop_tile_worker()
        center_x, center_y = self.center_world
        self.tiles = {}
        self.update()
        self.tile_worker = MapTileWorker(center_x * 256, center_y * 256, self.zoom)
        self.tile_worker.tiles_ready.connect(self._tiles_loaded)
        self.tile_worker.start()

    def set_center(self, lat: float, lon: float, emit=True):
        self.lat, self.lon = lat, lon
        self.center_world = _latlon_to_world(lat, lon, self.zoom)
        self._load_tiles()
        if emit:
            self.locationSelected.emit(lat, lon)

    def _tiles_loaded(self, tile_data):
        self.tiles = {}
        for key, data in tile_data.items():
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.tiles[key] = pixmap
        self.update()

    def zoom_by(self, delta: int):
        new_zoom = max(5, min(17, self.zoom + delta))
        if new_zoom == self.zoom:
            return
        self.zoom = new_zoom
        self.center_world = _latlon_to_world(self.lat, self.lon, self.zoom)
        self._load_tiles()

    def wheelEvent(self, event):
        self.zoom_by(1 if event.angleDelta().y() > 0 else -1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.position()
            self.press_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.drag_start is None:
            return
        dx = event.position().x() - self.drag_start.x()
        dy = event.position().y() - self.drag_start.y()
        cx, cy = self.center_world
        self.center_world = (cx - dx / 256, cy - dy / 256)
        self.drag_start = event.position()
        self.lat, self.lon = _world_to_latlon(*self.center_world, self.zoom)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.setCursor(Qt.ArrowCursor)
        click_distance = (
            abs(self.press_pos.x() - event.position().x())
            + abs(self.press_pos.y() - event.position().y())
            if self.press_pos is not None
            else 999
        )
        if click_distance < 4:
            origin_x = self.center_world[0] * 256 - self.width() / 2
            origin_y = self.center_world[1] * 256 - self.height() / 2
            world_x = (origin_x + event.position().x()) / 256
            world_y = (origin_y + event.position().y()) / 256
            self.lat, self.lon = _world_to_latlon(world_x, world_y, self.zoom)
            self.center_world = _latlon_to_world(self.lat, self.lon, self.zoom)
        self.locationSelected.emit(self.lat, self.lon)
        self.drag_start = None
        self.press_pos = None
        self._load_tiles()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.lightGray)
        origin_x = self.center_world[0] * 256 - self.width() / 2
        origin_y = self.center_world[1] * 256 - self.height() / 2
        for (tx, ty), pixmap in self.tiles.items():
            painter.drawPixmap(int(tx * 256 - origin_x), int(ty * 256 - origin_y), pixmap)
        cx, cy = self.width() // 2, self.height() // 2
        painter.setBrush(Qt.red)
        painter.drawEllipse(cx - 6, cy - 6, 12, 12)
        painter.drawText(8, self.height() - 8, "© OpenStreetMap contributors")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mizansene — Okala food finder")
        self.resize(900, 760)
        self.store = ProductStore(DB_PATH)
        self.worker = None
        self.store_worker = None
        self.current_products = {}
        self.search_categories = []
        self.loaded_category_count = 0
        self.settings = QSettings("Mizansene", "Mizansene")

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        self.title_label = QLabel("Mizansene")
        self.title_label.setStyleSheet("font-size: 22px; font-weight: 700;")
        title_row.addWidget(self.title_label)
        title_row.addStretch()
        self.recipes_button = QPushButton("📖 Recipe notebook")
        self.recipes_button.clicked.connect(self.open_recipes)
        title_row.addWidget(self.recipes_button)
        self.language_combo = QComboBox()
        self.language_combo.addItem("فارسی", "fa")
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Deutsch", "de")
        self.language_combo.setCurrentIndex(
            {"fa": 0, "en": 1, "de": 2}.get(
                self.settings.value("language", "en"), 1
            )
        )
        self.language_combo.currentIndexChanged.connect(self.change_language)
        title_row.addWidget(self.language_combo)
        layout.addLayout(title_row)

        self.location_box = QGroupBox("Location")
        location_box = self.location_box
        location_layout = QVBoxLayout(location_box)
        coordinate_row = QHBoxLayout()
        self.latitude = QLineEdit(str(self.settings.value("latitude", "")))
        self.longitude = QLineEdit(str(self.settings.value("longitude", "")))
        self.latitude.setPlaceholderText("Latitude")
        self.longitude.setPlaceholderText("Longitude")
        coordinate_row.addWidget(self.latitude)
        coordinate_row.addWidget(self.longitude)
        location_layout.addLayout(coordinate_row)

        map_row = QHBoxLayout()
        self.map_toggle = QPushButton("📍 Choose on map")
        self.map_toggle.setCheckable(True)
        self.map_toggle.toggled.connect(self.toggle_map)
        map_row.addWidget(self.map_toggle)
        zoom_out = QPushButton("−")
        zoom_out.setFixedWidth(34)
        zoom_out.clicked.connect(lambda: self.map.zoom_by(-1))
        map_row.addWidget(zoom_out)
        zoom_in = QPushButton("+")
        zoom_in.setFixedWidth(34)
        zoom_in.clicked.connect(lambda: self.map.zoom_by(1))
        map_row.addWidget(zoom_in)
        self.save_location_button = QPushButton("Save")
        self.save_location_button.clicked.connect(self.save_location)
        map_row.addWidget(self.save_location_button)
        self.find_stores_button = QPushButton("Find nearby stores")
        self.find_stores_button.clicked.connect(self.discover_stores)
        map_row.addWidget(self.find_stores_button)
        location_layout.addLayout(map_row)

        initial_lat = float(self.settings.value("latitude", 32.5))
        initial_lon = float(self.settings.value("longitude", 53.7))
        self.map = MapWidget(initial_lat, initial_lon)
        self.map.locationSelected.connect(self.set_map_location)
        self.map.hide()
        location_layout.addWidget(self.map)
        layout.addWidget(location_box)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("مثلاً: عدس پلو، شیر، مرغ، رب گوجه")
        self.search.returnPressed.connect(self.start_search)
        search_row.addWidget(self.search, 3)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.start_search)
        self.category_combo = QComboBox()
        self.category_combo.addItem("Smart category", "__smart__")
        for slug, _, label in FOOD_CATEGORIES:
            self.category_combo.addItem(label, slug)
        search_row.addWidget(self.category_combo, 1)

        self.store_combo = QComboBox()
        self.store_combo.setMinimumWidth(220)
        self.store_combo.addItem("Choose a nearby store", None)
        self.store_combo.currentIndexChanged.connect(self.store_changed)
        search_row.addWidget(self.store_combo, 1)

        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("Store ID:"))
        self.manual_store = QLineEdit()
        self.manual_store.setPlaceholderText("Optional")
        manual_row.addWidget(self.manual_store)
        self.use_manual_button = QPushButton("Use ID")
        self.use_manual_button.clicked.connect(self.use_manual_store)
        manual_row.addWidget(self.use_manual_button)
        self.selected_store_label = QLabel("Selected: —")
        manual_row.addWidget(self.selected_store_label)
        layout.addLayout(manual_row)

        self.history_label = QLabel()
        self.history_label.setWordWrap(True)
        layout.addWidget(self.history_label)
        self.clear_history_button = QPushButton("Clear search history")
        self.clear_history_button.clicked.connect(self.clear_history)
        layout.addWidget(self.clear_history_button)

        self.status = QLabel("Choose a location, store and search.")
        layout.addWidget(self.status)

        self.results = QListWidget()
        self.results.setUniformItemSizes(False)
        layout.addWidget(self.results, 1)

        self.load_more = QPushButton("Load more categories")
        self.load_more.clicked.connect(self.load_more_categories)
        self.load_more.hide()
        layout.addWidget(self.load_more)

        self.setCentralWidget(root)
        self.apply_language(self.language_combo.currentData())

    def change_language(self, index: int):
        code = self.language_combo.itemData(index)
        self.settings.setValue("language", code)
        self.apply_language(code)

    def apply_language(self, code: str):
        texts = {
            "en": {
                "location": "Location",
                "map": "📍 Choose on map",
                "hide_map": "📍 Hide map",
                "save": "Save",
                "stores": "Find nearby stores",
                "search": "Search",
                "use_id": "Use ID",
                "history": "Recent",
                "none": "none",
                "clear": "Clear search history",
                "recipes": "📖 Recipe notebook",
                "load_more": "Load more categories",
            },
            "fa": {
                "location": "موقعیت",
                "map": "📍 انتخاب روی نقشه",
                "hide_map": "📍 بستن نقشه",
                "save": "ذخیره",
                "stores": "پیدا کردن فروشگاه‌های نزدیک",
                "search": "جستجو",
                "use_id": "استفاده از شناسه",
                "history": "جستجوهای اخیر",
                "none": "هیچ‌کدام",
                "clear": "پاک کردن تاریخچه جستجو",
                "recipes": "📖 دفترچه رسپی",
                "load_more": "بارگذاری دسته‌های بیشتر",
            },
            "de": {
                "location": "Standort",
                "map": "📍 Auf Karte auswählen",
                "hide_map": "📍 Karte schließen",
                "save": "Speichern",
                "stores": "Nahe Geschäfte finden",
                "search": "Suchen",
                "use_id": "ID verwenden",
                "history": "Letzte Suchen",
                "none": "keine",
                "clear": "Suchverlauf löschen",
                "recipes": "📖 Rezeptbuch",
                "load_more": "Weitere Kategorien laden",
            },
        }[code]
        self.location_box.setTitle(texts["location"])
        self.map_toggle.setText(texts["hide_map"] if self.map_toggle.isChecked() else texts["map"])
        self.save_location_button.setText(texts["save"])
        self.find_stores_button.setText(texts["stores"])
        self.search_button.setText(texts["search"])
        self.use_manual_button.setText(texts["use_id"])
        self.recipes_button.setText(texts["recipes"])
        self.clear_history_button.setText(texts["clear"])
        self.load_more.setText(texts["load_more"])
        recent = self.store.recent_searches()
        self.history_label.setText(
            f"{texts['history']}: " + (" • ".join(recent) if recent else texts["none"])
        )

    def clear_history(self):
        self.store.clear_search_history()
        self.apply_language(self.language_combo.currentData())

    def toggle_map(self, visible: bool):
        self.map.setVisible(visible)
        self.map_toggle.setText("📍 Hide map" if visible else "📍 Choose on map")
        if visible:
            location = self.location_values()
            if location:
                self.map.set_center(*location, emit=False)

    def open_recipes(self):
        dialog = RecipeDialog(self.store, self)
        dialog.exec()

    def save_location(self):
        location = self.location_values()
        if location is None:
            QMessageBox.warning(
                self,
                "Invalid location",
                "Enter valid decimal latitude and longitude.",
            )
            return
        lat, lon = location
        self.settings.setValue("latitude", lat)
        self.settings.setValue("longitude", lon)
        self.map.set_center(lat, lon, emit=False)
        self.status.setText("Location saved.")

    def set_map_location(self, lat: float, lon: float):
        self.latitude.setText(f"{lat:.6f}")
        self.longitude.setText(f"{lon:.6f}")
        self.settings.setValue("latitude", lat)
        self.settings.setValue("longitude", lon)
        self.status.setText(f"Map location: {lat:.5f}, {lon:.5f}")

    def location_values(self):
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
            QMessageBox.warning(self, "Set location", "Enter a valid latitude and longitude first.")
            return
        self.save_location()
        self.status.setText("Finding nearby Okala stores…")
        self.store_combo.clear()
        self.store_combo.addItem("Finding stores…", None)
        self.store_combo.setEnabled(False)
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
            self.status.setText(f"Found {len(stores)} nearby stores.")
        else:
            self.status.setText("No nearby Okala stores were returned.")

    def store_changed(self, _index: int):
        store_id = self.store_combo.currentData()
        if store_id is None:
            self.selected_store_label.setText("Selected: —")
        else:
            self.manual_store.clear()
            self.selected_store_label.setText(f"Selected: {int(store_id)}")

    def use_manual_store(self):
        try:
            store_id = int(self.manual_store.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid store ID", "Store ID must be a number.")
            return
        self.store_combo.setCurrentIndex(0)
        self.selected_store_label.setText(f"Selected: {store_id}")
        self.status.setText(f"Using store {store_id}.")

    def selected_store_id(self):
        value = self.store_combo.currentData()
        if value is not None:
            return int(value)
        raw = self.manual_store.text().strip()
        return int(raw) if raw.isdigit() else None

    def start_search(self):
        query = self.search.text().strip()
        store_id = self.selected_store_id()
        if not query:
            return
        if store_id is None:
            QMessageBox.information(self, "Choose a store", "Select or enter a store ID first.")
            return

        self.store.add_search(query)
        self.search_categories = categories_for_query(query, self.category_combo.currentData())
        self.loaded_category_count = min(3, len(self.search_categories))
        self.results.clear()
        self.current_products.clear()
        self.load_more.hide()
        self._run_categories(self.search_categories[: self.loaded_category_count], store_id)
        self.load_more.setVisible(self.loaded_category_count < len(self.search_categories))

    def _run_categories(self, categories, store_id):
        labels = ", ".join(item[2] for item in categories)
        self.status.setText(f"Searching {labels}…")
        self.worker = SearchWorker(self.search.text().strip(), store_id, categories)
        self.worker.batch.connect(self.show_batch)
        self.worker.finished.connect(self.show_results)
        self.worker.failed.connect(self.show_error)
        self.worker.start()

    def show_batch(self, products):
        self._render_products(products)
        self.status.setText(f"Loaded {len(products)} matches. More results can be loaded below.")

    def show_results(self, products):
        self._render_products(products)
        self.store.save_products(products)
        if not products:
            self.status.setText("No matching available products found in the selected category.")
        else:
            self.status.setText(f"Loaded {len(products)} matching products.")
        self.load_more.setVisible(self.loaded_category_count < len(self.search_categories))

    def load_more_categories(self):
        if self.worker and self.worker.isRunning():
            return
        store_id = self.selected_store_id()
        if store_id is None:
            return
        next_count = min(self.loaded_category_count + 3, len(self.search_categories))
        categories = self.search_categories[self.loaded_category_count : next_count]
        self.loaded_category_count = next_count
        self._run_categories(categories, store_id)
        self.load_more.setVisible(self.loaded_category_count < len(self.search_categories))

    def _render_products(self, products):
        for product in products:
            self.current_products[product.id] = product
        merged = list(self.current_products.values())
        self.results.clear()
        for product in merged[:30]:
            item = QListWidgetItem()
            widget = ProductItem(product)
            item.setSizeHint(widget.sizeHint())
            self.results.addItem(item)
            self.results.setItemWidget(item, widget)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(3000)
        if self.store_worker and self.store_worker.isRunning():
            self.store_worker.requestInterruption()
            self.store_worker.wait(3000)
        self.map.close()
        super().closeEvent(event)

    def show_error(self, message: str):
        self.store_combo.setEnabled(True)
        self.status.setText("Request failed.")
        QMessageBox.warning(self, "Okala error", message)
