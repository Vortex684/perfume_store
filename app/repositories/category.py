from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


async def get_by_id(db: AsyncSession, category_id: UUID) -> Category | None:
    result = await db.execute(select(Category).where(Category.id == category_id))
    return result.scalar_one_or_none()


async def get_by_slug(db: AsyncSession, slug: str) -> Category | None:
    result = await db.execute(select(Category).where(Category.slug == slug))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, obj: Category) -> Category:
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_multi(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Category]:
    result = await db.execute(select(Category).where(Category.is_active == True).offset(skip).limit(limit))
    return result.scalars().all()