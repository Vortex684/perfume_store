from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand


async def get_by_id(db: AsyncSession, brand_id: UUID) -> Brand | None:
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    return result.scalar_one_or_none()


async def get_by_slug(db: AsyncSession, slug: str) -> Brand | None:
    result = await db.execute(select(Brand).where(Brand.slug == slug))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, obj: Brand) -> Brand:
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_multi(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Brand]:
    result = await db.execute(select(Brand).where(Brand.is_active == True).offset(skip).limit(limit))
    return result.scalars().all()