import uuid

from sqlalchemy import Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import decimal 
from app.models.base import BaseModel


class CartItem(BaseModel):
    __tablename__ = "cart_items"

    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")