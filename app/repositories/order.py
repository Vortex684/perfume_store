"""
Order repository.

All SQL queries for orders live here.
Separates data access from business logic.
"""
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory


async def get_by_id(db: AsyncSession, order_id: UUID) -> Order | None:
    """Fetch a single order with all related data."""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.payments),
        )
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def get_by_order_number(db: AsyncSession, order_number: str) -> Order | None:
    """Fetch order by human-readable order number."""
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.payments),
        )
        .where(Order.order_number == order_number)
    )
    return result.scalar_one_or_none()


async def get_by_user(
    db: AsyncSession,
    user_id: UUID,
    skip: int = 0,
    limit: int = 20,
) -> list[Order]:
    """Fetch all orders for a specific customer."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user_id)
        .order_by(desc(Order.created_at))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_all(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
) -> tuple[list[Order], int]:
    """Fetch all orders with optional status filter. Returns (orders, total_count)."""
    from sqlalchemy import func

    query = select(Order)
    count_query = select(func.count()).select_from(Order)

    if status:
        query = query.where(Order.status == status)
        count_query = count_query.where(Order.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    result = await db.execute(
        query.options(selectinload(Order.items), selectinload(Order.user))
        .order_by(desc(Order.created_at))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all(), total

