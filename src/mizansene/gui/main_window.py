from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QComboBox, QVBoxLayout, QWidget,
)

from mizansene.config import (
    CACHE_DIR, DB_PATH, OKALA_LAT, OKALA_LON, OKALA_STORE_ID, OKALA_TOKEN
)
from mizansene.crawler.client import OkalaClient, OkalaError
from mizansene.crawler.recipes import ingredients_for
from mizansene.crawler.search import extract_products, rank_products
from mizansene.crawler.stores import extract_stores
from mizansene.database.store import ProductStore


FOOD_CATEGORIES = [
    ("groceries", 1461), ("dairy-products", 1462), ("proteins", 1463),
    ("canned-ready-food", 1464), ("beverages", 1465), ("breakfast-goods", 1466),
    ("nuts-sweets", 1468), ("spices", 1469), ("fruits-vegetables", 1470),
]


class SearchWorker(QThread):
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, query: str, store_id: int | None):
        super().__init__()
        self.query = query
        self.store_id = store_id

    def run(self):
        client = OkalaClient(token=OKALA_TOKEN, cache_dir=CACHE_DIR)
        try:
            ingredients = ingredients_for(self.query)
            terms = ingredients or [self.query]

            if not self.store_id:
                raise OkalaError("Select a nearby Okala store before searching.")
            products = []
                for slug, category_id in FOOD_CATEGORIES:
                    payload = client.store_category(self.store_id, slug, category_id)
                    products.extend(extract_products(payload, self.store_id, available_only=True))

                # A recipe produces a useful combined shopping result. Products
                # are scored against every ingredient and deduplicated by ID.
                if ingredients:
                    ranked: list[tuple[int, object]] = []
                    for product in products:
                        score = sum(
                            1 for ingredient in terms
                            if ingredient.casefold() in product.name.casefold()
                        )
                        if score:
                            ranked.append((score, product))
                    products = [p for _, p in sorted(
                        ranked, key=lambda pair: (pair[0], -len(pair[1].name)), reverse=True
                    )]
                else:
                    products = rank_products(products, self.query)

            self.finished.emit(products[:60])
        except OkalaError as exc:
            self.failed.emit(str(exc))
        finally:
            client.close()


class StoreWorker(QThread):
    finished = Signal(list)
    failed = Signal(str)

    def run(self):
        if OKALA_LAT is None or OKALA_LON is None:
            self.failed.emit(
                "Set OKALA_LAT and OKALA_LON to your location before finding nearby stores."
            )
            return
        client = OkalaClient(token=OKALA_TOKEN, cache_dir=CACHE_DIR)
        try:
            payload = client.nearby("groceries", OKALA_LAT, OKALA_LON)
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
            try:
                import httpx
                response = httpx.get(product.image_url, timeout=8)
                response.raise_for_status()
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                image.setPixmap(
                    pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            except Exception:
                pass
        layout.addWidget(image)

        text = QVBoxLayout()
        name = QLabel(product.name)
        name.setWordWrap(True)
        name.setStyleSheet("font-size: 15px; font-weight: 600;")
        text.addWidget(name)
        if product.price is not None:
            text.addWidget(QLabel(f"{product.price:,} تومان"))
        if product.url:
            button = QPushButton("Open in Okala")
            button.clicked.connect(lambda: webbrowser.open(product.url))
            text.addWidget(button)
        layout.addLayout(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mizansene — Okala food finder")
        self.resize(860, 760)
        self.store = ProductStore(DB_PATH)
        self.worker = None
        self.store_worker = None

        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("What do you want to cook or buy?")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(title)

        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("مثلاً: عدس پلو، شیر، مرغ، رب گوجه")
        self.search.returnPressed.connect(self.start_search)
        row.addWidget(self.search)

        self.store_combo = QComboBox()
        self.store_combo.setMinimumWidth(230)
        self.store_combo.addItem("Select a nearby store", None)
        if OKALA_STORE_ID:
            self.store_combo.addItem(f"Configured store: {OKALA_STORE_ID}", int(OKALA_STORE_ID))
            self.store_combo.setCurrentIndex(1)
        row.addWidget(self.store_combo)

        discover = QPushButton("Find nearby stores")
        discover.clicked.connect(self.discover_stores)
        row.addWidget(discover)

        button = QPushButton("Search")
        button.clicked.connect(self.start_search)
        row.addWidget(button)
        layout.addLayout(row)

        self.manual_store = QLineEdit(OKALA_STORE_ID or "")
        self.manual_store.setPlaceholderText("Or enter Okala store ID")
        layout.addWidget(self.manual_store)

        recent = self.store.recent_searches()
        history = QLabel("Recent: " + (" • ".join(recent) if recent else "none"))
        history.setWordWrap(True)
        layout.addWidget(history)

        self.status = QLabel("Set your coordinates, find nearby stores, then select a store.")
        layout.addWidget(self.status)
        self.results = QListWidget()
        layout.addWidget(self.results)
        self.setCentralWidget(root)

    def selected_store_id(self) -> int | None:
        combo_value = self.store_combo.currentData()
        if combo_value is not None:
            return int(combo_value)
        raw = self.manual_store.text().strip()
        return int(raw) if raw else None

    def discover_stores(self):
        self.status.setText("Finding nearby Okala stores…")
        self.store_worker = StoreWorker()
        self.store_worker.finished.connect(self.show_stores)
        self.store_worker.failed.connect(self.show_error)
        self.store_worker.start()

    def show_stores(self, stores):
        self.store_combo.clear()
        self.store_combo.addItem("Choose a nearby store", None)
        for store_id, name in stores:
            self.store_combo.addItem(f"{name} ({store_id})", store_id)
        self.status.setText(f"Found {len(stores)} nearby stores. Select one before searching.")

    def start_search(self):
        query = self.search.text().strip()
        if not query:
            return
        try:
            store_id = self.selected_store_id()
        except ValueError:
            QMessageBox.warning(self, "Invalid store ID", "Store ID must be a number.")
            return

        if store_id is None:
            QMessageBox.information(
                self,
                "Choose a store",
                "Find nearby stores and select a store first, or enter an Okala store ID.",
            )
            return

        self.store.add_search(query)
        self.status.setText("Searching selected Okala store…")
        self.results.clear()
        self.worker = SearchWorker(query, store_id)
        self.worker.finished.connect(self.show_results)
        self.worker.failed.connect(self.show_error)
        self.worker.start()

    def show_results(self, products):
        self.results.clear()
        if not products:
            self.status.setText("No matching products found.")
            return
        self.status.setText(f"Found {len(products)} candidates.")
        self.store.save_products(products)
        for product in products:
            item = QListWidgetItem()
            widget = ProductItem(product)
            item.setSizeHint(widget.sizeHint())
            self.results.addItem(item)
            self.results.setItemWidget(item, widget)

    def show_error(self, message: str):
        self.status.setText("Request failed.")
        QMessageBox.warning(self, "Okala error", message)
