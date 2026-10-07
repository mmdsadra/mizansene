from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

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
    available: Mapped[bool | None] = mapped_column(nullable=True)
    store_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class SearchRow(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ProductStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(self.engine)

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
                row.available = product.available
                row.store_id = product.store_id
                row.last_seen = datetime.now(timezone.utc)

    def add_search(self, query: str) -> None:
        with self.Session.begin() as session:
            session.add(SearchRow(query=query.strip()))

    def recent_searches(self, limit: int = 10) -> list[str]:
        with self.Session() as session:
            rows = session.scalars(
                select(SearchRow).order_by(SearchRow.created_at.desc()).limit(limit)
            ).all()
            return [row.query for row in rows]
