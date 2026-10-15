"""
Inventory business logic.

Core rules:
1. Every stock change creates an InventoryTransaction (audit trail).
2. quantity_available can never go below 0.
3. Admin adjustments must include a reason.
4. Low stock is determined by: available <= threshold.

Preventing overselling:
When a customer checks out, we reserve inventory:
- available -= quantity
- reserved += quantity

When payment succeeds:
- reserved -= quantity
- sold += quantity

When payment fails or order is cancelled:
- reserved -= quantity
- available += quantity
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Inventory
from app.models.inventory_transaction import InventoryTransaction, TransactionType
from app.models.product_variant import ProductVariant
from app.repositories import inventory as inventory_repo

async def get_inventory(db: AsyncSession, variant_id: UUID) -> Inventory | None:
    """Fetch current inventory for a variant."""
    return await inventory_repo.get_by_variant_id(db, variant_id)

async def adjust_inventory(
    db: AsyncSession,
    variant_id: UUID,
    quantity_change: int,
    transaction_type: TransactionType,
    changed_by: UUID | None = None,
    reason: str | None = None,
    reference_id: UUID | None = None,
) -> Inventory:
    """
    Adjust inventory and log the transaction.

    quantity_change:
      +5 = add 5 units to available stock
      -2 = remove 2 units from available stock

    Raises ValueError if adjustment would make available stock negative.
    """
    
    # Fetch inventory with variant info
    result = await db.execute(
        select(Inventory)
        .options(selectinload(Inventory.variant))
        .where(Inventory.variant_id == variant_id)
    )
    inventory = result.scalar_one_or_none()
    
    if not inventory:
        raise ValueError("Inventory record not found for this variant")

    # Validate: cannot make available stock negative
    new_available = inventory.quantity_available + quantity_change
    if new_available < 0:
        raise ValueError(
            f"Cannot reduce stock by {abs(quantity_change)}. "
            f"Only {inventory.quantity_available} available."
        )
        
    inventory.quantity_available = new_available
    
    # Log transaction
    transaction = InventoryTransaction(
        variant_id=variant_id,
        quantity_change=quantity_change,
        transaction_type=transaction_type,
        reference_id=reference_id,
        reason=reason or f"{transaction_type.value} adjustment",
        changed_by=changed_by,
    )
    db.add(transaction)

    await db.commit()
    await db.refresh(inventory)
    return inventory

async def get_low_stock_items(db: AsyncSession) -> list[Inventory]:
    """Return all variants where available stock is at or below threshold."""
    return await inventory_repo.get_all_inventory(db, low_stock_only=True)

async def get_inventory_history(
    db: AsyncSession,
    variant_id: UUID,
) -> list[InventoryTransaction]:
    """Return complete audit trail for a variant."""
    return await inventory_repo.get_transactions_for_variant(db, variant_id)

async def set_low_stock_threshold(
    db: AsyncSession,
    variant_id: UUID,
    threshold: int,
) -> Inventory:
    """Admin changes the low-stock alert threshold for a variant."""
    
    result = await db.execute(
        select(Inventory).where(Inventory.variant_id == variant_id)
    )
    inventory = result.scalar_one_or_none()
    if not inventory:
        raise ValueError("Inventory not found")
    
    inventory.low_stock_threshold = threshold
    await db.commit()
    await db.refresh(inventory)
    return inventory