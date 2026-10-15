"""
Order model.

This is the core transactional record. Every purchase creates exactly one Order.
The order status tracks fulfillment. The payment_status tracks money.

Why separate order_status and payment_status?
A COD order can be SHIPPED (fulfillment) but still PENDING (payment).
A Stripe order can be PAID (payment) but still PENDING (not yet shipped).
"""
import uuid
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import String, Boolean, Enum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class OrderStatus(str, PyEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class PaymentStatus(str, PyEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class Order(BaseModel):
    __tablename__ = "orders"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    
    # Status tracking
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False
    )

    # Address snapshots (we freeze these at order time so changes to user profile don't affect past orders)
    shipping_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    billing_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Financials - all calculated server-side, never trusted from frontend
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    shipping_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory", back_populates="order", cascade="all, delete-orphan"
    )