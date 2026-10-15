"""Pydantic request/response schemas for returns and refunds."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict

from app.models.return_request import ReturnReason, ReturnStatus
from app.models.refund import RefundStatus

class ReturnItemCreate(BaseModel):
    # The service checks this quantity against the purchased quantity
    # and all earlier non-rejected return requests.
    order_item_id: uuid.UUID

    # A customer cannot request zero or a negative number of items.
    quantity: int = Field(ge=1)

    # This is only the customer's report of the item's condition.
    # The admin must inspect the physical item before restocking it.
    customer_condition: Literal[
        "unopened",
        "opened",
        "damaged",
    ] | None = None

class ReturnItemResponse(BaseModel):
    # Allow Pydantic to read values directly from SQLAlchemy model objects.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_item_id: uuid.UUID

    # These are read-only properties provided by the ReturnItem model.
    product_name: str
    sku: str

    quantity: int
    condition: str
    customer_condition: str | None
    
class ReturnRequestCreate(BaseModel):
    # The original order the customer wants to return items from.
    order_id: uuid.UUID

    reason: ReturnReason

    # Keep optional customer notes within a reasonable size.
    customer_notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    # A return request must contain at least one item.
    items: list[ReturnItemCreate] = Field(min_length=1)

class ReturnRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    status: ReturnStatus
    reason: ReturnReason
    customer_notes: str | None
    admin_notes: str | None
    items: list[ReturnItemResponse]
    created_at: datetime

class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    status: RefundStatus
    reason: str | None
    processed_by: uuid.UUID | None
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime | None
    manual_reference: str | None
    failure_note: str | None
    created_at: datetime

class ReturnItemConditionUpdate(BaseModel):
    # The admin must submit the condition found during physical inspection.
    order_item_id: uuid.UUID

    condition: Literal[
        "unopened",
        "opened",
        "damaged",
    ]

class AdminReturnUpdate(BaseModel):
    # REFUNDED is intentionally excluded.
    # Only the refund-confirmation service may set that status.
    status: Literal[
        ReturnStatus.APPROVED,
        ReturnStatus.REJECTED,
        ReturnStatus.ITEMS_RECEIVED,
    ] | None = None

    admin_notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    # Required when marking items as received.
    # Each returned order line must have an admin-confirmed condition.
    received_conditions: list[ReturnItemConditionUpdate] | None = None
    
    
class ProcessRefundRequest(BaseModel):
    # This creates a PENDING record; it does not transfer money.
    amount: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )

    reason: str | None = Field(
        default=None,
        max_length=255,
    )
    
class ConfirmManualRefundRequest(BaseModel):
    # The caller must explicitly confirm the real transfer occurred.
    confirm_transfer: Literal[True]

    # Require a receipt or transaction reference for audit purposes.
    manual_reference: str = Field(
        min_length=1,
        max_length=255,
    )


class FailManualRefundRequest(BaseModel):
    # Record why the manual transfer attempt did not succeed.
    failure_note: str = Field(
        min_length=1,
        max_length=2000,
    )