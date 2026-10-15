"""
Inventory transaction model.

Every single change to inventory is logged here.
This is the audit trail that answers:
- Why did stock change?
- Who changed it?
- When did it change?

Transaction types:
- SALE: customer purchase (decreases available)
- RESTOCK: new shipment arrived (increases available)
- RETURN: customer returned item (increases available)
- ADJUSTMENT: manual correction by admin
- RESERVATION: item reserved during checkout (moves available → reserved)
"""
import uuid
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import String, Integer, ForeignKey, Numeric, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class TransactionType(str, PyEnum):
    SALE = "sale"
    RESTOCK = "restock"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    RESERVATION = "reservation"


class InventoryTransaction(BaseModel):
    __tablename__ = "inventory_transactions"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    # Positive = stock increased (restock, return)
    # Negative = stock decreased (sale, reservation)

    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    
    # Reference to what caused this change (order_id, return_id, etc.)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Human-readable reason
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Who made the change (null for system/automated)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    variant: Mapped["ProductVariant"] = relationship("ProductVariant")