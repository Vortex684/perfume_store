import uuid
from decimal import Decimal

from sqlalchemy import String, Boolean, ForeignKey, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ProductVariant(BaseModel):
    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    size_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    images: Mapped[list["ProductImage"]] = relationship("ProductImage", back_populates="variant")
    inventory: Mapped["Inventory | None"] = relationship("Inventory", back_populates="variant", uselist=False)