
"""
Checkout endpoint.

This converts a cart into an order.
The frontend calls this when the user clicks "Place Order".

Currently supported:
- COD: Creates the order with payment pending.

Online payments will be added later through Safepay.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.order import OrderCreate, CheckoutResponse
from app.services import cart_service, order_service

router = APIRouter()


@router.post("", response_model=CheckoutResponse)
async def create_checkout(
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create an order from the user's cart.

    Authentication is required for checkout.
    Currently, only Cash on Delivery is supported.
    """

    # 1. Ensure the user is authenticated
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required for checkout",
        )

    # 2. Validate the payment method before creating an order
    if order_in.payment_method.lower() != "cod":
        raise HTTPException(
            status_code=400,
            detail="Currently, only Cash on Delivery is available.",
        )

    # 3. Get the user's cart
    cart = await cart_service.get_or_create_cart(
        db,
        user_id=current_user.id,
    )

    # 4. Ensure the cart contains items
    if not cart.items:
        raise HTTPException(
            status_code=400,
            detail="Cart is empty",
        )

    # 5. Create the order
    try:
        order, _ = await order_service.create_order_from_cart(
            db,
            cart,
            order_in,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    # 6. Return checkout response
    return CheckoutResponse(
        order_id=order.id,
        order_number=order.order_number,
        payment_method=order_in.payment_method,
        amount=order.grand_total,
        currency=order.currency,
    ) 