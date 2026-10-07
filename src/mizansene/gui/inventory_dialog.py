from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QDoubleSpinBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from mizansene.config import CACHE_DIR
from mizansene.crawler.inventory import find_food_image
from mizansene.database.store import ProductStore
from mizansene.gui.image_loader import ImageLoadWorker


class InventoryDialog(QDialog):
    def __init__(self, store: ProductStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.worker: ImageLoadWorker | None = None
        self.setWindowTitle("Inventory")
        self.resize(760, 560)

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("مثلاً: برنج عنبربو طلایی")
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0, 100000000)
        self.quantity.setDecimals(1)
        self.quantity.setSuffix(" g")
        form.addRow("Item", self.name)
        form.addRow("Quantity", self.quantity)
        root.addLayout(form)

        actions = QHBoxLayout()
        add = QPushButton("Add / update")
        add.clicked.connect(self.save_item)
        actions.addWidget(add)
        delete = QPushButton("Delete selected")
        delete.clicked.connect(self.delete_selected)
        actions.addWidget(delete)
        refresh = QPushButton("Refresh images")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        actions.addStretch()
        root.addLayout(actions)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self.select_item)
        root.addWidget(self.list, 1)
        self.status = QLabel("")
        root.addWidget(self.status)
        self.reload()

    def reload(self):
        self.list.clear()
        for row in self.store.list_inventory():
            item = QListWidgetItem()
            item.setData(Qt.UserRole, row)
            self.list.addItem(item)
        self._render()
        self._load_images()

    def _render(self):
        for index in range(self.list.count()):
            item = self.list.item(index)
            row = item.data(Qt.UserRole)
            widget = QWidget()
            layout = QHBoxLayout(widget)
            image = QLabel("Image")
            image.setFixedSize(64, 64)
            image.setAlignment(Qt.AlignCenter)
            image.setStyleSheet("border: 1px solid #ddd; color: #888;")
            image.setObjectName(f"image_{row['id']}")
            layout.addWidget(image)
            text = QLabel(f"{row['name']}\n{row['quantity_grams']:g} g")
            text.setWordWrap(True)
            layout.addWidget(text, 1)
            item.setSizeHint(widget.sizeHint())
            self.list.setItemWidget(item, widget)

    def _load_images(self):
        items = []
        for index in range(self.list.count()):
            row = self.list.item(index).data(Qt.UserRole)
            if row.get("image_url"):
                items.append((str(row["id"]), row["image_url"]))
        if not items:
            return
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(2000)
        self.worker = ImageLoadWorker(items, CACHE_DIR / "images")
        self.worker.image_ready.connect(self._image_ready)
        self.worker.start()

    def _image_ready(self, key: str, data: bytes):
        for index in range(self.list.count()):
            item = self.list.item(index)
            if str(item.data(Qt.UserRole)["id"]) != key:
                continue
            widget = self.list.itemWidget(item)
            label = widget.findChild(QLabel, f"image_{key}")
            if label is not None:
                pixmap = QPixmap()
                if pixmap.loadFromData(data):
                    label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            break

    def select_item(self, current, _previous):
        if current is None:
            return
        row = current.data(Qt.UserRole)
        self.name.setText(row["name"])
        self.quantity.setValue(float(row["quantity_grams"]))

    def save_item(self):
        name = self.name.text().strip()
        quantity = float(self.quantity.value())
        if not name or quantity <= 0:
            QMessageBox.warning(self, "Inventory", "Enter an item name and a positive quantity.")
            return
        image = find_food_image(name)
        self.store.add_inventory_item(name, quantity, image_url=image)
        self.status.setText("Saved. Image lookup completed." if image else "Saved. No image was found.")
        self.name.clear()
        self.quantity.setValue(0)
        self.reload()

    def delete_selected(self):
        item = self.list.currentItem()
        if item is None:
            return
        row = item.data(Qt.UserRole)
        self.store.delete_inventory_item(int(row["id"]))
        self.reload()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(3000)
        super().closeEvent(event)
