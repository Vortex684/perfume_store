"""
OrderItem model.

Each row represents one line item in an order.
We SNAPSHOT prices here. If the product price changes tomorrow,
this order still shows what the customer actually paid.
"""
import uuid
from decimal import Decimal

from sqlalchemy import String, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class OrderItem(BaseModel):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True
    )
    
    # Snapshots - these are frozen at purchase time
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    variant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")