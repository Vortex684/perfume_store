from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by email. Returns None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """Fetch a user by primary key."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none() 

async def create_user(db: AsyncSession, obj_in: UserCreate) -> User:
    """
    Create a new user. The password is hashed HERE before touching the database.
    Never pass plaintext passwords into SQLAlchemy models.
    """
    db_obj = User(
        email=obj_in.email,
        hashed_password=get_password_hash(obj_in.password),
        first_name=obj_in.first_name,
        last_name=obj_in.last_name,
        phone=obj_in.phone,
    )
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj