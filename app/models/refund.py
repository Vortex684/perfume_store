"""Refund record. COD refunds are manual; no payment gateway is called."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class RefundStatus(str, PyEnum):
    # Refund record exists, but the transfer is not confirmed.
    PENDING = "pending"

    # Admin verified that the money was actually transferred.
    SUCCEEDED = "succeeded"

    # Admin recorded a failed or aborted manual transfer.
    FAILED = "failed"


class Refund(BaseModel):
    __tablename__ = "refunds"

    __table_args__ = (
        # Prevent zero or negative refund amounts at database level.
        CheckConstraint(
            "amount > 0",
            name="ck_refunds_amount_positive",
        ),
    )

    # One refund record per return request.
    return_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("return_requests.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Numeric is used for money rather than floating-point arithmetic.
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # A newly created refund remains PENDING until manually confirmed.
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refundstatus"),
        default=RefundStatus.PENDING,
        nullable=False,
    )

    # Reserved for a possible future payment-gateway integration.
    # Phase 8 does not call any gateway.
    gateway_refund_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Admin who created/processed the refund record.
    processed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Admin who confirmed that the manual transfer actually happened.
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamp of manual confirmation, including timezone information.
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Bank transfer, wallet transaction, or other receipt/reference identifier.
    manual_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Explanation recorded when a manual refund attempt fails.
    failure_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # One-to-one relationship back to the return request.
    return_request: Mapped["ReturnRequest"] = relationship(
        "ReturnRequest",
        back_populates="refund",
    )