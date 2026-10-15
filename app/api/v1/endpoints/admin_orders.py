"""
Admin order management endpoints.

Admins can:
- List all orders with filters
- View any order
- Update order status (processing, shipped, delivered)
- Cancel orders
- Mark COD as paid
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.order import OrderStatus
from app.schemas.order import OrderResponse
from app.services import order_service
from app.repositories import order as order_repo

router = APIRouter()

@router.get("", response_model=list[OrderResponse])
async def list_all_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
):
    """Admin: list all orders with optional status filter."""
    orders, total = await order_repo.get_all(db, skip=skip, limit=limit, status=status)
    return orders

@router.get("/{order_id}", response_model=OrderResponse)
async def get_any_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: view any order regardless of owner."""
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.put("/{order_id}/status")
async def update_order_status(
    order_id: UUID,
    new_status: str,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin: update order status.
    Valid statuses: pending, confirmed, processing, shipped, delivered, cancelled, returned
    """
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        status_enum = OrderStatus(new_status.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    try:
        updated = await order_service.update_order_status(
            db, order, status_enum, changed_by=current_user.id, reason=reason
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    
@router.post("/{order_id}/cancel")
async def admin_cancel_order(
    order_id: UUID,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    
    """Admin: cancel any order that hasn't shipped yet."""
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    try:
        await order_service.cancel_order(db, order, changed_by=current_user.id, reason=reason or "Cancelled by admin")
        return {"message": "Order cancelled"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/{order_id}/cod-collected")
async def mark_cod_collected(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: mark a COD order as paid after collecting cash."""
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    try:
        await order_service.mark_cod_payment_collected(db, order, changed_by=current_user.id)
        return {"message": "COD payment marked as collected"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))