from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.product_image import ProductImage
from app.models.inventory import Inventory


async def get_by_id(db: AsyncSession, product_id: UUID) -> Product | None:
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.brand),
            selectinload(Product.category),
        )
        .where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


async def get_by_slug(db: AsyncSession, slug: str) -> Product | None:
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.brand),
            selectinload(Product.category),
        )
        .where(Product.slug == slug, Product.is_active == True)
    )
    return result.scalar_one_or_none()


async def create(db: AsyncSession, obj: Product) -> Product:
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_multi(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    gender: str | None = None,
    category_id: UUID | None = None,
    brand_id: UUID | None = None,
    is_featured: bool | None = None,
) -> tuple[list[Product], int]:
    query = select(Product).where(Product.is_active == True)
    count_query = select(func.count()).select_from(Product).where(Product.is_active == True)

    if gender:
        query = query.where(Product.gender == gender)
        count_query = count_query.where(Product.gender == gender)
    if category_id:
        query = query.where(Product.category_id == category_id)
        count_query = count_query.where(Product.category_id == category_id)
    if brand_id:
        query = query.where(Product.brand_id == brand_id)
        count_query = count_query.where(Product.brand_id == brand_id)
    if is_featured is not None:
        query = query.where(Product.is_featured == is_featured)
        count_query = count_query.where(Product.is_featured == is_featured)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    result = await db.execute(
        query.options(
        selectinload(Product.images),
        selectinload(Product.brand),
        selectinload(Product.category),
    )
        .offset(skip)
        .limit(limit)
        .order_by(Product.created_at.desc())
    )
    return result.scalars().all(), total