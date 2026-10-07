from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from mizansene.config import CACHE_DIR, DB_PATH, OKALA_LAT, OKALA_LON, OKALA_STORE_ID, OKALA_TOKEN
from mizansene.crawler.client import OkalaClient, OkalaError
from mizansene.crawler.search import extract_products, rank_products
from mizansene.database.store import ProductStore


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
            # These are intentionally conservative defaults for the first MVP.
            # The next crawler iteration can discover the user's nearby store
            # and category IDs instead of requiring a fixed category.
            if not self.store_id:
                payload = client.nearby("groceries", OKALA_LAT, OKALA_LON)
            else:
                # 1461 is the grocery root category used by existing Okala clients.
                payload = client.store_category(self.store_id, "groceries", 1461)

            products = rank_products(extract_products(payload, self.store_id), self.query)
            self.finished.emit(products[:40])
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
        if product.image_url:
            try:
                import httpx
                data = httpx.get(product.image_url, timeout=8).content
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                image.setPixmap(pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception:
                pass
        layout.addWidget(image)

        text = QVBoxLayout()
        name = QLabel(product.name)
        name.setWordWrap(True)
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
        self.resize(760, 700)
        self.store = ProductStore(DB_PATH)
        self.worker = None

        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("What do you want to cook or buy?")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(title)

        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("e.g. عدس پلو، شیر، مرغ، رب گوجه")
        self.search.returnPressed.connect(self.start_search)
        row.addWidget(self.search)

        self.store_id = QLineEdit(OKALA_STORE_ID or "")
        self.store_id.setPlaceholderText("Store ID (optional)")
        self.store_id.setMaximumWidth(170)
        row.addWidget(self.store_id)

        button = QPushButton("Search")
        button.clicked.connect(self.start_search)
        row.addWidget(button)
        layout.addLayout(row)

        self.history = QComboBox()
        self.history.addItem("Recent searches")
        self.history.addItems(self.store.recent_searches())
        self.history.currentTextChanged.connect(self.use_history)
        layout.addWidget(self.history)

        self.status = QLabel("Ready.")
        layout.addWidget(self.status)

        self.results = QListWidget()
        layout.addWidget(self.results)
        self.setCentralWidget(root)

    def use_history(self, text: str):
        if text and text != "Recent searches":
            self.search.setText(text)

    def start_search(self):
        query = self.search.text().strip()
        if not query:
            return
        try:
            store_id = int(self.store_id.text()) if self.store_id.text().strip() else None
        except ValueError:
            QMessageBox.warning(self, "Invalid store ID", "Store ID must be a number.")
            return

        self.store.add_search(query)
        self.status.setText("Searching Okala…")
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
        self.status.setText("Search failed.")
        QMessageBox.warning(self, "Okala error", message)
