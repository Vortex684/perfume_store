import uuid
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import String, Boolean, Enum, ForeignKey, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ProductGender(str, PyEnum):
    WOMEN = "women"
    MEN = "men"
    UNISEX = "unisex"


class Product(BaseModel):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    story: Mapped[str | None] = mapped_column(Text, nullable=True)  # Luxury marketing copy

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )

    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    gender: Mapped[ProductGender] = mapped_column(Enum(ProductGender), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    brand: Mapped["Brand"] = relationship("Brand", back_populates="products")
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    images: Mapped[list["ProductImage"]] = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    fragrance_notes: Mapped[list["ProductFragranceNote"]] = relationship("ProductFragranceNote", back_populates="product", cascade="all, delete-orphan")