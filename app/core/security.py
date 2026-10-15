"""
Security primitives.

This module handles:
- Password hashing (Argon2)
- JWT creation and verification

Why Argon2?
It is memory-hard, meaning it resists GPU/ASIC cracking far better than bcrypt
in modern threat models. It won the Password Hashing Competition (PHC).

Why JWT for access tokens?
They are stateless. The server does not need to query a database to verify
a token. This keeps auth checks fast. The trade-off is revocation: a stolen
access token is valid until it expires. We mitigate this by keeping the lifetime
very short (15 minutes) and using refresh tokens for the long-lived session.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# CryptContext lets us swap hashing algorithms later without touching
# business logic. "argon2" is the current scheme.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare a plain password against its Argon2 hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plain password with Argon2. Never store plaintext."""
    return pwd_context.hash(password)


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """
    Create a short-lived JWT access token.
    'subject' is usually the user_id (UUID as string).
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str | Any) -> str:
    """
    Create a long-lived JWT refresh token.
    Refresh tokens are stored in the database so they can be revoked.
    """
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """
    Decode and validate a JWT. Returns None if invalid or expired.
    We return None instead of raising so callers decide how to handle failure.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        return None