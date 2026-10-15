"""
Customer order endpoints.

Customers can:
- View their own orders
- View order details
- Cancel their own order (only if not yet shipped)
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.schemas.order import OrderResponse
from app.services import order_service
from app.repositories import order as order_repo

router = APIRouter()


@router.get("", response_model=list[OrderResponse])
async def list_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 20,
):
    """Return all orders for the currently logged-in customer."""
    orders = await order_service.get_user_orders(db, current_user.id, skip, limit)
    return orders


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order_detail(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return a single order. Customers can only view their own orders."""
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return order


@router.post("/{order_id}/cancel")
async def cancel_my_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Customer cancels their own order before it ships."""
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        await order_service.cancel_order(db, order, changed_by=current_user.id, reason="Cancelled by customer")
        return {"message": "Order cancelled successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))