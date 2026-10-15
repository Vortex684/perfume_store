"""
Order schemas.

Separate schemas for creation, response, and list views.
The response includes nested items and status history.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.order import OrderStatus, PaymentStatus


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_name: str
    variant_name: str | None
    sku: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderStatusHistoryResponse(BaseModel):
    from_status: str | None
    to_status: str
    reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    shipping_address: dict
    billing_address: dict | None = None
    payment_method: str  # "stripe" or "cod"
    notes: str | None = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    status: OrderStatus
    payment_status: PaymentStatus
    shipping_address: dict | None
    billing_address: dict | None
    subtotal: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    discount_total: Decimal
    grand_total: Decimal
    currency: str
    notes: str | None
    items: list[OrderItemResponse]
    status_history: list[OrderStatusHistoryResponse]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckoutResponse(BaseModel):
    """
    Response from POST /checkout.

    For Stripe: includes client_secret for frontend to complete payment.
    For COD: just confirms order creation.
    """

    order_id: uuid.UUID
    order_number: str
    payment_method: str
    client_secret: str | None = None  # Only for Stripe
    amount: Decimal
    currency: str