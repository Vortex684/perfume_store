"""Database model for a customer's return request."""

import uuid
from enum import Enum as PyEnum

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

class ReturnStatus(str, PyEnum):
    # A customer submitted the request; an admin must review it.
    REQUESTED = "requested"

    # The admin has accepted the request.
    APPROVED = "approved"

    # The admin rejected the request.
    REJECTED = "rejected"

    # The store physically received and inspected the returned items.
    ITEMS_RECEIVED = "items_received"

    # Set only after a manual refund transfer has been confirmed.
    REFUNDED = "refunded"
    
class ReturnReason(str, PyEnum):
    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    NOT_AS_DESCRIBED = "not_as_described"
    CHANGED_MIND = "changed_mind"
    OTHER = "other"
    
class ReturnRequest(BaseModel):
    __tablename__ = "return_requests"

    # The original order associated with this return.
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )

    # The customer who submitted the request.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # New requests begin in REQUESTED state.
    status: Mapped[ReturnStatus] = mapped_column(
        Enum(ReturnStatus, name="returnstatus"),
        default=ReturnStatus.REQUESTED,
        nullable=False,
    )

    # Why the customer wants to return the items.
    reason: Mapped[ReturnReason] = mapped_column(
        Enum(ReturnReason, name="returnreason"),
        nullable=False,
    )
    
    customer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Optional internal notes entered by the admin.
    admin_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # back_populates keeps both sides of the ORM relationships consistent.
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="return_requests",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="return_requests",
    )
    
    # One request can contain multiple returned order items.
    items: Mapped[list["ReturnItem"]] = relationship(
        "ReturnItem",
        back_populates="return_request",
        cascade="all, delete-orphan",
    )
    
    # One refund record per return request.
    # The refund amount can be lower than the eligible total,
    # so this also supports a partial refund.
    refund: Mapped["Refund | None"] = relationship(
        "Refund",
        back_populates="return_request",
        uselist=False,
    )