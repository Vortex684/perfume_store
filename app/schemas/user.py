import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Shared user fields."""
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    
class UserCreate(UserBase):
    """
    Fields required to register.
    Password is plain here; hashing happens in the service.
    """
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    
    
class UserResponse(UserBase):
    """What the API returns. Never includes the password hash."""
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    role: UserRole
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserBase):
    """Internal schema that includes the hash. Used only inside the backend."""
    hashed_password: str