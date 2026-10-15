"""
Authentication endpoints.

Register  → creates a user (no auth required)
Login     → validates credentials, returns access token + sets refresh cookie
Refresh   → reads httpOnly cookie, issues new access token
Logout    → revokes refresh cookie
Me        → returns current user profile
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm  
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.api.deps import get_db, get_current_active_user
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse
from app.models.user import User
from app.services import auth_service
from app.core.config import get_settings

settings = get_settings()
router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new customer account.
    Password is validated by Pydantic (min 8 chars) then hashed by Argon2.
    """
    try:
        user = await auth_service.register_user(db, user_in)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

 
@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth2-compatible login.
    The client sends form data: username=<email>&password=<pass>.
    We return a short-lived access token in the JSON body,
    and a long-lived refresh token in an httpOnly cookie.

    Why httpOnly?
    JavaScript cannot read it. This prevents XSS attacks from stealing
    the refresh token via document.cookie.

    Why secure=False in development?
    Localhost usually lacks HTTPS. In production, COOKIE_SECURE=True
    so the browser only sends the cookie over HTTPS.
    """
    user = await auth_service.authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(str(user.id))
    refresh_token = await auth_service.create_refresh_token_entry(db, user.id)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    
    return Token(
        access_token=access_token,
        token_type='bearer',
        expires_in= settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Token rotation endpoint.
    The frontend calls this when the access token expires (every 15 min).
    We read the refresh token from the httpOnly cookie, validate it,
    issue a NEW access token, and ROTATE the refresh token.

    Why rotate?
    If an attacker steals a refresh token, it becomes useless after the
    legitimate client rotates it. This limits the window of attack.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    try:
        result = await auth_service.refresh_access_token(db, refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # Rotate: revoke old refresh token, issue new one
    await auth_service.revoke_refresh_token(db, refresh_token)
    new_refresh = await auth_service.create_refresh_token_entry(db, UUID(result["user_id"]))

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return Token(
        access_token=result['access_token'],
        token_type='bearer',
        expires_in= settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
     )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Revoke the refresh token and clear the cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await auth_service.revoke_refresh_token(db, refresh_token)

    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Return the currently authenticated user's profile."""
    return current_user



