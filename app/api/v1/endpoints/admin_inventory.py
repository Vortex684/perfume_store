"""
Admin inventory management endpoints.

Admins can:
- View all inventory
- View low stock alerts
- Adjust stock levels (restock, adjustment)
- View inventory history/audit trail
- Set low stock thresholds
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.inventory_transaction import TransactionType
from app.schemas.inventory import (
    InventoryResponse,
    InventoryTransactionCreate,
    InventoryTransactionResponse,
    LowStockAlert,
)
from app.services import inventory_service
from app.repositories import inventory as inventory_repo

router = APIRouter()


@router.get("", response_model=list[InventoryResponse])
async def list_inventory(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    low_stock_only: bool = False,
):
    """Admin: view all inventory or filter for low stock items."""
    items = await inventory_repo.get_all_inventory(db, skip=skip, limit=limit, low_stock_only=low_stock_only)
    
    result = []
    for inv in items:
        result.append(InventoryResponse(
            variant_id=inv.variant_id,
            product_name=inv.variant.product.name,
            sku=inv.variant.sku,
            size_ml=inv.variant.size_ml,
            quantity_available=inv.quantity_available,
            quantity_reserved=inv.quantity_reserved,
            quantity_sold=inv.quantity_sold,
            low_stock_threshold=inv.low_stock_threshold,
        ))
    return result


@router.get("/low-stock", response_model=list[LowStockAlert])
async def low_stock_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: view products that are at or below their low stock threshold."""
    items = await inventory_service.get_low_stock_items(db)
    
    result = []
    for inv in items:
        result.append(LowStockAlert(
            variant_id=inv.variant_id,
            product_name=inv.variant.product.name,
            sku=inv.variant.sku,
            quantity_available=inv.quantity_available,
            low_stock_threshold=inv.low_stock_threshold,
        ))
    return result


@router.post("/adjust", response_model=InventoryResponse)
async def adjust_stock(
    adjustment: InventoryTransactionCreate,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin: adjust inventory for a variant.

    Examples:
    - Restock: quantity_change=+10, type=restock
    - Correction: quantity_change=-2, type=adjustment
    """
    try:
        updated = await inventory_service.adjust_inventory(
            db,
            variant_id=adjustment.variant_id,
            quantity_change=adjustment.quantity_change,
            transaction_type=adjustment.transaction_type,
            changed_by=current_user.id,
            reason=reason,
        )
        return InventoryResponse(
            variant_id=updated.variant_id,
            product_name=updated.variant.product.name,
            sku=updated.variant.sku,
            size_ml=updated.variant.size_ml,
            quantity_available=updated.quantity_available,
            quantity_reserved=updated.quantity_reserved,
            quantity_sold=updated.quantity_sold,
            low_stock_threshold=updated.low_stock_threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history/{variant_id}", response_model=list[InventoryTransactionResponse])
async def view_inventory_history(
    variant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Admin: view complete audit trail for a specific variant."""
    transactions = await inventory_repo.get_transactions_for_variant(db, variant_id, skip, limit)
    return transactions


@router.put("/threshold/{variant_id}")
async def set_threshold(
    variant_id: UUID,
    threshold: int = Query(..., ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):  
    """Admin: change the low-stock alert threshold for a variant."""
    try:
        updated = await inventory_service.set_low_stock_threshold(db, variant_id, threshold)
        return {
            "variant_id": str(updated.variant_id),
            "low_stock_threshold": updated.low_stock_threshold,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))