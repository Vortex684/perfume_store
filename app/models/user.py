import uuid
from enum import Enum as PyEnum

from sqlalchemy import String, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class UserRole(str, PyEnum):
    """Role-based access control levels."""
    CUSTOMER = "customer"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class User(BaseModel):
    """
    The users table stores all accounts: customers, admins, superadmins.
    Passwords are NEVER stored plaintext. Only the Argon2 hash.
    """
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Account flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.CUSTOMER, nullable=False)

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    # Add this to User model
    carts: Mapped[list["Cart"]] = relationship("Cart", back_populates="user", cascade="all, delete-orphan")
    
    orders = relationship( "Order", back_populates="user",)