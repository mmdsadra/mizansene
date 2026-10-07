from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from mizansene.crawler.recipes import RECIPES
from mizansene.models import Product


class Base(DeclarativeBase):
    pass


class ProductRow(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(nullable=True)
    available: Mapped[bool | None] = mapped_column(nullable=True)
    store_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class SearchRow(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class RecipeRow(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, index=True)
    ingredients: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_title: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class ProductStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self._migrate_product_columns()
        self.Session = sessionmaker(self.engine)

    def _migrate_product_columns(self) -> None:
        # create_all() does not add columns to an existing SQLite table.
        with self.engine.begin() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(products)").fetchall()
            }
            if "original_price" not in columns:
                connection.exec_driver_sql("ALTER TABLE products ADD COLUMN original_price INTEGER")
            if "discount_percent" not in columns:
                connection.exec_driver_sql("ALTER TABLE products ADD COLUMN discount_percent FLOAT")

    def save_products(self, products: list[Product]) -> None:
        with self.Session.begin() as session:
            for product in products:
                row = session.get(ProductRow, product.id)
                if row is None:
                    row = ProductRow(id=product.id)
                    session.add(row)
                row.name = product.name
                row.url = product.url
                row.image_url = product.image_url
                row.price = product.price
                row.original_price = product.original_price
                row.discount_percent = product.discount_percent
                row.available = product.available
                row.store_id = product.store_id
                row.last_seen = datetime.now(timezone.utc)

    def add_search(self, query: str) -> None:
        with self.Session.begin() as session:
            session.add(SearchRow(query=query.strip()))

    def clear_search_history(self) -> None:
        with self.Session.begin() as session:
            session.query(SearchRow).delete()

    def recent_searches(self, limit: int = 10) -> list[str]:
        with self.Session() as session:
            rows = session.scalars(
                select(SearchRow).order_by(SearchRow.created_at.desc()).limit(limit)
            ).all()
            return [row.query for row in rows]

    def upsert_recipe(
        self,
        name: str,
        ingredients: str,
        instructions: str,
        source_url: str | None = None,
        source_title: str | None = None,
        recipe_id: int | None = None,
    ) -> int:
        with self.Session.begin() as session:
            row = session.get(RecipeRow, recipe_id) if recipe_id else None
            if row is None and source_url:
                row = session.scalars(
                    select(RecipeRow).where(RecipeRow.source_url == source_url)
                ).first()
            if row is None:
                row = RecipeRow(name=name)
                session.add(row)
            row.name = name.strip()
            row.ingredients = ingredients
            row.instructions = instructions
            row.source_url = source_url
            row.source_title = source_title
            row.updated_at = datetime.now(timezone.utc)
            session.flush()
            return int(row.id)

    def delete_recipe(self, recipe_id: int) -> None:
        with self.Session.begin() as session:
            row = session.get(RecipeRow, recipe_id)
            if row is not None:
                session.delete(row)

    def ensure_seed_recipes(self) -> None:
        with self.Session.begin() as session:
            exists = session.scalar(select(RecipeRow.id).limit(1))
            if exists is not None:
                return
            for name, ingredients in RECIPES.items():
                session.add(
                    RecipeRow(
                        name=name,
                        ingredients="\n".join(ingredients),
                        instructions="Recipe ingredients from the offline starter dictionary.",
                    )
                )

    def list_recipes(self) -> list[dict]:
        with self.Session() as session:
            rows = session.scalars(select(RecipeRow).order_by(RecipeRow.name)).all()
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "ingredients": row.ingredients,
                    "instructions": row.instructions,
                    "source_url": row.source_url,
                    "source_title": row.source_title,
                }
                for row in rows
            ]
