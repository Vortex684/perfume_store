import uuid
from datetime import datetime, timedelta

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

class Cart(BaseModel):
    __tablename__ = "carts"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    session_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(datetime.timezone.utc) + timedelta(days=7),
        nullable=False,
    )
    user: Mapped["User | None"] = relationship("User", back_populates="carts")
    items: Mapped[list["CartItem"]] = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")