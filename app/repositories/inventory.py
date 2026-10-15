"""
Inventory repository.

Handles all SQL for inventory queries and updates.
"""
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Inventory
from app.models.inventory_transaction import InventoryTransaction
from app.models.product_variant import ProductVariant


async def get_by_variant_id(db: AsyncSession, variant_id: UUID) -> Inventory | None:
    """Fetch inventory record for a specific variant."""
    result = await db.execute(
        select(Inventory)
        .options(selectinload(Inventory.variant).selectinload(ProductVariant.product))
        .where(Inventory.variant_id == variant_id)
    )
    return result.scalar_one_or_none()

async def get_all_inventory(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    low_stock_only: bool = False,
) -> list[Inventory]:
    """
    Fetch inventory records.
    If low_stock_only=True, only return items where available <= threshold.
    """

    query = select(Inventory).options(
        selectinload(Inventory.variant).selectinload(ProductVariant.product)
    )

    if low_stock_only:
        query = query.where(
            Inventory.quantity_available <= Inventory.low_stock_threshold
        )

    result = await db.execute(
        query.order_by(Inventory.quantity_available.asc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_transactions_for_variant(
    db: AsyncSession,
    variant_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[InventoryTransaction]:
    """Fetch audit history for a specific variant."""
    
    result = await db.execute(
        select(InventoryTransaction)
        .where(InventoryTransaction.variant_id == variant_id)
        .order_by(InventoryTransaction.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_transaction(
    db: AsyncSession,
    transaction: InventoryTransaction,
) -> InventoryTransaction:
    """Log an inventory change in the audit table."""
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return transaction

