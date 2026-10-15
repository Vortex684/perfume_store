"""One line item and quantity included in a return request."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ReturnItem(BaseModel):
    __tablename__ = "return_items"
     
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_return_items_quantity_positive",
        ),
    )
    
    # The return request this item belongs to.
    return_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("return_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # The specific line item from the original order.
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    # How many units of this order item the customer wants to return.
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    
    # The store's actual inspection result.
    # It starts pending; customer input must not determine restocking.
    condition: Mapped[str] = mapped_column(
        String(50),
        default="pending_inspection",
        nullable=False,
    )
    
    # Optional customer-reported condition.
    # This is informational only and cannot authorize restocking.
    customer_condition: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # ORM relationships.
    return_request: Mapped["ReturnRequest"] = relationship(
        "ReturnRequest",
        back_populates="items",
    )
    
    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem",
    )


    # Expose the original purchase-time product name without duplicating
    # product_name in this table. This relies on OrderItem's snapshot fields.
    @property
    def product_name(self) -> str:
        return self.order_item.product_name

    # Expose the original SKU in the same way.
    @property
    def sku(self) -> str:
        return self.order_item.sku