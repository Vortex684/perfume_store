from pydantic import BaseModel


class Token(BaseModel):
    """Response when login or refresh succeeds."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseModel):
    """The decoded contents of a JWT."""
    sub: str | None = None  # subject (user_id)
    type: str | None = None  # "access" or "refresh"