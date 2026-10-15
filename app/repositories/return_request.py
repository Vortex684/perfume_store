"""Database queries for return requests. Business rules stay in the service."""

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.return_item import ReturnItem
from app.models.return_request import ReturnRequest, ReturnStatus

async def get_by_id(
    db: AsyncSession,
    return_id: UUID,
) -> ReturnRequest | None:
    """Load relationships required by the response schemas and service logic."""
    result = await db.execute(
        select(ReturnRequest)
        .options(
            # Load returned items and their original order-item snapshots.
            selectinload(ReturnRequest.items).selectinload(
                ReturnItem.order_item
            ),
            selectinload(ReturnRequest.refund),
            selectinload(ReturnRequest.order),
        )
        .where(ReturnRequest.id == return_id)
    )

    return result.scalar_one_or_none()

async def get_by_user(
    db: AsyncSession,
    user_id: UUID,
    skip: int = 0,
    limit: int = 20,
) -> list[ReturnRequest]:
    """Return a paginated list belonging to one customer."""
    result = await db.execute(
        select(ReturnRequest)
        .options(
            selectinload(ReturnRequest.items).selectinload(
                ReturnItem.order_item
            ),
            selectinload(ReturnRequest.refund),
        )
        # Filtering here prevents customers from listing other users' returns.
        .where(ReturnRequest.user_id == user_id)
        .order_by(desc(ReturnRequest.created_at))
        .offset(skip)
        .limit(limit)
    )

    return list(result.scalars().all())

async def get_all(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    status: ReturnStatus | None = None,
) -> list[ReturnRequest]:
    """Allow admins to list returns, optionally filtered by status."""
    query = select(ReturnRequest).options(
        selectinload(ReturnRequest.items).selectinload(
            ReturnItem.order_item
        ),
        selectinload(ReturnRequest.user),
        selectinload(ReturnRequest.order),
        selectinload(ReturnRequest.refund),
    )
    
    # Add the filter only when the admin supplied a status.
    if status is not None:
        query = query.where(ReturnRequest.status == status)

    result = await db.execute(
        query
        .order_by(desc(ReturnRequest.created_at))
        .offset(skip)
        .limit(limit)
    )

    return list(result.scalars().all())