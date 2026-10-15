import uuid
from enum import Enum as PyEnum

from sqlalchemy import String, Boolean, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class GenderTarget(str, PyEnum):
    WOMEN = "women"
    MEN = "men"
    UNISEX = "unisex"


class Category(BaseModel):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gender_target: Mapped[GenderTarget | None] = mapped_column(Enum(GenderTarget), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Self-referencing: parent category
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True
    )
    parent: Mapped["Category | None"] = relationship("Category", remote_side="Category.id", back_populates="children")
    children: Mapped[list["Category"]] = relationship("Category", back_populates="parent")

    # Relationship to products
    products: Mapped[list["Product"]] = relationship("Product", back_populates="category")  