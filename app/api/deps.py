"""
FastAPI Dependencies.

These functions are injected into routes using Depends().
They handle:
- Database session lifecycle
- Current user extraction from JWT
- Optional current user extraction for guest/user routes
- Role-based access control

The request flow for protected routes:
HTTP Request
    → FastAPI Router
    → Depends(get_current_user)
    → JWT decode
    → DB lookup
    → Route handler

The request flow for optional-auth routes:
HTTP Request
    → FastAPI Router
    → Depends(get_optional_current_user)
    → JWT exists? → Decode + DB lookup
    → No JWT? → Return None
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user import get_user_by_id
from app.core.security import decode_token


# Used by protected endpoints.
# If the request does not contain:
# Authorization: Bearer <token>
# FastAPI automatically returns 401 Unauthorized.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)


# Used by endpoints where authentication is optional.
#
# auto_error=False means:
# - Token exists → we can authenticate the user.
# - Token does not exist → return None instead of raising 401.
#
# This is useful for things like carts that work for both
# guests and logged-in users.
oauth2_optional_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    Get the authenticated user.

    Authentication is REQUIRED here.

    No token / invalid token → 401
    Valid token → return User object
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode the JWT access token.
    payload = decode_token(token)

    if payload is None:
        raise credentials_exception

    # The user's ID is stored in the JWT "sub" claim.
    user_id: str | None = payload.get("sub")

    # Make sure this is actually an access token.
    if user_id is None or payload.get("type") != "access":
        raise credentials_exception

    # Find the user in the database.
    user = await get_user_by_id(db, UUID(user_id))

    if user is None:
        raise credentials_exception

    # Don't allow inactive users to access protected routes.
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Inactive user",
        )

    return user


async def get_optional_current_user(
    db: AsyncSession = Depends(get_db),
    token: str | None = Depends(oauth2_optional_scheme),
) -> User | None:
    """
    Get the current user if authenticated.

    Authentication is OPTIONAL here.

    No token → return None
    Valid token → return User object
    Invalid token → return None

    This is useful for endpoints that support both
    guests and authenticated users, such as the cart.
    """

    # Guest request: no Authorization header.
    if token is None:
        return None

    # Try to decode the JWT.
    payload = decode_token(token)

    if payload is None:
        return None

    # Extract user ID from the JWT.
    user_id: str | None = payload.get("sub")

    # Make sure this is an access token.
    if user_id is None or payload.get("type") != "access":
        return None

    # Find the user in the database.
    user = await get_user_by_id(db, UUID(user_id))

    if user is None or not user.is_active:
        return None

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Shortcut dependency that ensures the user is authenticated
    and active.

    get_current_user() already performs the active-user check.
    """

    return current_user


def require_role(required_role: UserRole):
    """
    Factory that creates a role-checking dependency.

    Usage:

        current_user: User = Depends(
            require_role(UserRole.ADMIN)
        )

    Superadmin bypasses all role checks.
    """

    def _role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:

        # Superadmin has access to everything.
        if current_user.role == UserRole.SUPERADMIN:
            return current_user

        # Reject users who don't have the required role.
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return _role_checker


# Pre-built dependency for admin-only routes.
require_admin = require_role(UserRole.ADMIN)