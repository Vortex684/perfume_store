"""
Payment model.

Tracks all payment attempts for an order.
One order can have multiple payments (retry after failure, partial payments).
"""
import uuid
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import String, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class PaymentMethod(str, PyEnum):
    STRIPE = "stripe"
    COD = "cod"


class PaymentStatus(str, PyEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Payment(BaseModel):
    __tablename__ = "payments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    
    # Stripe-specific
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    # Store raw Stripe response for debugging and dispute evidence
    payment_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="payments")