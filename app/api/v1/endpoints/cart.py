import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Cookie,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_optional_current_user
from app.models.user import User
from app.schemas.cart import (
    CartItemCreate,
    CartItemUpdate,
    CartResponse,
)
from app.services import cart_service


router = APIRouter()


async def get_cart_dependency(
    db: AsyncSession = Depends(get_db),

    # Authentication is OPTIONAL for carts.
    #
    # Logged-in user → User object
    # Guest → None
    current_user: User | None = Depends(get_optional_current_user),

    # FastAPI reads the guest's session_id from the cookie.
    session_id: Annotated[str | None, Cookie()] = None,

    # FastAPI provides the outgoing Response object.
    # We use it to create/delete the guest session cookie.
    response: Response = None,
):
    """
    Resolve the correct cart for the request.

    Two possible situations:

    1. Logged-in user
       → use the user's cart

    2. Guest
       → use/create a cart identified by session_id cookie

    If a guest logs in while carrying a guest cart,
    the guest cart is merged into the user's cart.
    """

    # ─────────────────────────────────────────────
    # LOGGED-IN USER
    # ─────────────────────────────────────────────

    if current_user:

        # If the user still has a guest session cookie,
        # they may have items in their guest cart.
        #
        # Merge those items into their authenticated cart.
        if session_id:

            cart = await cart_service.merge_guest_cart_into_user_cart(
                db,
                session_id,
                current_user.id,
            )

            # The guest cart has now been merged,
            # so the old guest cookie is no longer needed.
            if response:
                response.delete_cookie("session_id")

            return cart

        # No guest cart → simply get/create the user's cart.
        return await cart_service.get_or_create_cart(
            db,
            user_id=current_user.id,
        )

    # ─────────────────────────────────────────────
    # GUEST USER
    # ─────────────────────────────────────────────

    # No session cookie means this is a completely
    # new guest.
    if not session_id:

        # Generate a secure random identifier for this guest.
        session_id = cart_service.generate_session_id()

        # Send the session ID back to the browser as a cookie.
        if response:
            response.set_cookie(
                key="session_id",
                value=session_id,

                # JavaScript cannot access this cookie.
                httponly=True,

                # False for local development.
                # Must be True when using HTTPS in production.
                secure=False,

                # Helps protect against cross-site request attacks.
                samesite="lax",

                # Guest cart expires from the browser after 7 days.
                max_age=7 * 24 * 60 * 60,
            )

    # Get the existing guest cart or create a new one.
    return await cart_service.get_or_create_cart(
        db,
        session_id=session_id,
    )


@router.get("", response_model=CartResponse)
async def get_cart(
    cart=Depends(get_cart_dependency),
):
    """
    Get the current user's or guest's cart.
    """

    return cart_service.build_cart_response(cart)


@router.post("/items", response_model=CartResponse)
async def add_item(
    item_in: CartItemCreate,
    db: AsyncSession = Depends(get_db),
    cart=Depends(get_cart_dependency),
):
    """
    Add a product variant to the cart.

    Works for both:
    - Guest users
    - Logged-in users
    """

    try:
        updated_cart = await cart_service.add_item_to_cart(
            db,
            cart,
            item_in,
        )

        return cart_service.build_cart_response(updated_cart)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.put("/items/{item_id}", response_model=CartResponse)
async def update_item(
    item_id: uuid.UUID,
    item_in: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    cart=Depends(get_cart_dependency),
):
    """
    Update the quantity of an item in the cart.

    quantity = 0 removes the item.
    """

    try:
        updated_cart = await cart_service.update_cart_item(
            db,
            cart,
            item_id,
            item_in,
        )

        return cart_service.build_cart_response(updated_cart)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.delete("/items/{item_id}", response_model=CartResponse)
async def remove_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    cart=Depends(get_cart_dependency),
):
    """
    Remove an item from the cart.

    Internally this sets the item's quantity to 0.
    """

    try:
        updated_cart = await cart_service.update_cart_item(
            db,
            cart,
            item_id,
            CartItemUpdate(quantity=0),
        )

        return cart_service.build_cart_response(updated_cart)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.delete("")
async def clear_cart(
    db: AsyncSession = Depends(get_db),
    cart=Depends(get_cart_dependency),
):
    """
    Remove all items from the current cart.
    """

    await cart_service.clear_cart(db, cart)

    return {"message": "Cart cleared"}