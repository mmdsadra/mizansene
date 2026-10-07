from __future__ import annotations

import webbrowser

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mizansene.crawler.recipes import import_yummy_gastronomy
from mizansene.database.store import ProductStore


class RecipeImportWorker(QThread):
    progress = Signal(str)
    finished = Signal(int)
    failed = Signal(str)

    def __init__(self, store: ProductStore):
        super().__init__()
        self.store = store

    def run(self):
        try:
            count = import_yummy_gastronomy(
                self.store.upsert_recipe,
                progress=self.progress.emit,
            )
            self.finished.emit(count)
        except Exception as exc:
            self.failed.emit(str(exc))


class RecipeDialog(QDialog):
    def __init__(self, store: ProductStore, parent=None, search_callback=None):
        super().__init__(parent)
        self.store = store
        self.store.ensure_seed_recipes()
        self.current_id: int | None = None
        self.search_callback = search_callback
        self.import_worker: RecipeImportWorker | None = None
        self.setWindowTitle("Recipe notebook")
        self.resize(900, 620)

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addWidget(QLabel("Recipes"))
        self.recipe_list = QListWidget()
        self.recipe_list.currentItemChanged.connect(self.select_recipe)
        left.addWidget(self.recipe_list)

        buttons = QHBoxLayout()
        new_button = QPushButton("New")
        new_button.clicked.connect(self.new_recipe)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self.delete_recipe)
        buttons.addWidget(new_button)
        buttons.addWidget(delete_button)
        left.addLayout(buttons)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        self.name = QTextEdit()
        self.name.setFixedHeight(42)
        self.name.setPlaceholderText("Recipe name")
        right.addWidget(self.name)

        right.addWidget(QLabel("Ingredients"))
        self.ingredients = QTextEdit()
        self.ingredients.setPlaceholderText("One ingredient per line")
        right.addWidget(self.ingredients)

        right.addWidget(QLabel("Instructions / notes"))
        self.instructions = QTextEdit()
        right.addWidget(self.instructions)

        self.source = QLabel("Source: —")
        self.source.setWordWrap(True)
        right.addWidget(self.source)

        actions = QHBoxLayout()
        save = QPushButton("Save recipe")
        save.clicked.connect(self.save_recipe)
        actions.addWidget(save)
        open_source = QPushButton("Open source")
        open_source.clicked.connect(self.open_source)
        actions.addWidget(open_source)
        shopping_button = QPushButton("Smart shopping")
        shopping_button.clicked.connect(self.smart_shopping)
        actions.addWidget(shopping_button)
        import_button = QPushButton("Import Yummy Gastronomy")
        import_button.clicked.connect(self.import_yummy)
        actions.addWidget(import_button)
        right.addLayout(actions)

        self.progress = QLabel("")
        self.progress.setWordWrap(True)
        right.addWidget(self.progress)
        root.addLayout(right, 2)

        self.reload()

    def reload(self):
        self.recipe_list.clear()
        for recipe in self.store.list_recipes():
            item = QListWidgetItem(recipe["name"])
            item.setData(256, recipe)
            self.recipe_list.addItem(item)
        if self.recipe_list.count():
            self.recipe_list.setCurrentRow(0)
        else:
            self.new_recipe()

    def select_recipe(self, current, _previous):
        if current is None:
            return
        recipe = current.data(256)
        self.current_id = recipe["id"]
        self.name.setPlainText(recipe["name"])
        self.ingredients.setPlainText(recipe["ingredients"])
        self.instructions.setPlainText(recipe["instructions"])
        source = recipe.get("source_url")
        self.source.setText(f"Source: {source or 'local recipe'}")

    def new_recipe(self):
        self.current_id = None
        self.name.clear()
        self.ingredients.clear()
        self.instructions.clear()
        self.source.setText("Source: local recipe")
        self.recipe_list.clearSelection()

    def save_recipe(self):
        name = self.name.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "Recipe", "Recipe name cannot be empty.")
            return
        recipe_id = self.store.upsert_recipe(
            name=name,
            ingredients=self.ingredients.toPlainText(),
            instructions=self.instructions.toPlainText(),
            source_url=self._source_url(),
            source_title=name,
            recipe_id=self.current_id,
        )
        self.current_id = recipe_id
        self.reload()

    def delete_recipe(self):
        if self.current_id is None:
            return
        self.store.delete_recipe(self.current_id)
        self.current_id = None
        self.reload()

    def _source_url(self) -> str | None:
        text = self.source.text()
        if text.startswith("Source: http"):
            return text[8:].strip()
        return None

    def open_source(self):
        url = self._source_url()
        if url:
            webbrowser.open(url)

    def smart_shopping(self):
        raw = [line.strip() for line in self.ingredients.toPlainText().splitlines()]
        ingredients = [line for line in raw if line and len(line) > 1]
        if not ingredients:
            QMessageBox.information(
                self,
                "Smart shopping",
                "This recipe has no ingredients yet.",
            )
            return
        suggestions = "\n".join(f"☐ {item}" for item in ingredients)
        box = QMessageBox(self)
        box.setWindowTitle("Smart shopping list")
        box.setText("Ingredients detected from this recipe:")
        box.setDetailedText(suggestions)
        if self.search_callback:
            search = box.addButton("Search first ingredient", QMessageBox.AcceptRole)
            box.exec()
            if box.clickedButton() is search:
                self.search_callback(ingredients[0])
        else:
            box.setInformativeText(suggestions)
            box.exec()

    def import_yummy(self):
        if self.import_worker and self.import_worker.isRunning():
            return
        self.progress.setText("Importing channel index only. Full descriptions require YouTube access.")
        self.import_worker = RecipeImportWorker(self.store)
        self.import_worker.progress.connect(self.progress.setText)
        self.import_worker.finished.connect(self.import_finished)
        self.import_worker.failed.connect(self.import_failed)
        self.import_worker.start()

    def import_finished(self, count: int):
        self.progress.setText(f"Imported/updated {count} YouTube recipes.")
        self.reload()

    def closeEvent(self, event):
        if self.import_worker and self.import_worker.isRunning():
            self.import_worker.requestInterruption()
            self.import_worker.wait(3000)
        super().closeEvent(event)

    def import_failed(self, message: str):
        self.progress.setText("YouTube import failed.")
        QMessageBox.warning(self, "Recipe import", message)
