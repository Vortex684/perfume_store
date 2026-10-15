"""
Authentication business logic.

This layer sits between the API (HTTP) and the Repository (SQL).
It decides:
- Is the password correct?
- Should we create a new refresh token?
- Is this token revoked?

If we removed this layer, routes would contain raw business rules,
making them untestable and tightly coupled to the database.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.user import UserCreate
from app.repositories import user as user_repo


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    """
    Verify credentials. Returns the user if email+password are valid AND active.
    Returns None for any failure (we do not reveal whether email or password was wrong).
    """
    user = await user_repo.get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


async def register_user(db: AsyncSession, obj_in: UserCreate) -> User:
    """Register a new customer. Raises ValueError if email exists."""
    existing = await user_repo.get_user_by_email(db, obj_in.email)
    if existing:
        raise ValueError("Email already registered")
    return await user_repo.create_user(db, obj_in)


async def create_refresh_token_entry(db: AsyncSession, user_id: UUID) -> str:
    """
    Generate a JWT refresh token AND persist it to the database.
    We store it so we can revoke it later (logout, password change, etc.).
    """
    token = create_refresh_token(str(user_id))
    expires = datetime.now(timezone.utc) + timedelta(days=7)

    db_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires,
    )
    db.add(db_token)
    await db.commit()
    return token


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> dict:
    """
    Validate a refresh token and issue a new access token.
    Steps:
    1. Decode the JWT (signature + expiry check).
    2. Look it up in the database (revocation check).
    3. Verify the user still exists and is active.
    4. Issue a new access token.
    """
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise ValueError("Invalid refresh token")

    # Database check: is this token revoked or expired?
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == refresh_token,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    db_token = result.scalar_one_or_none()
    if not db_token:
        raise ValueError("Refresh token not found or expired")

    user = await user_repo.get_user_by_id(db, UUID(payload["sub"]))
    if not user or not user.is_active:
        raise ValueError("User not found or inactive")

    access_token = create_access_token(str(user.id))
    return {
        "access_token": access_token,
        "user_id": str(user.id),
    }


async def revoke_refresh_token(db: AsyncSession, token: str) -> None:
    """Mark a refresh token as revoked. Used during logout."""
    result = await db.execute(select(RefreshToken).where(RefreshToken.token == token))
    db_token = result.scalar_one_or_none()
    if db_token:
        db_token.is_revoked = True
        await db.commit()


async def revoke_all_user_refresh_tokens(db: AsyncSession, user_id: UUID) -> None:
    """Revoke every refresh token for a user. Useful after password change or security breach."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked.is_(False),
        )
    )
    tokens = result.scalars().all()
    for t in tokens:
        t.is_revoked = True
    await db.commit()