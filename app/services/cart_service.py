
"""
Cart business logic.

Rules:
1. Guest carts use session_id.
2. Logged-in carts use user_id.
3. Existing items increase quantity.
4. Prices always come from the database.
5. Carts expire after 7 days.
"""

import uuid
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.product_variant import ProductVariant
from app.models.inventory import Inventory
from app.schemas.cart import (
    CartItemCreate,
    CartItemUpdate,
    CartItemResponse,
    CartResponse,
)


def generate_session_id() -> str:
    return secrets.token_urlsafe(32)


async def get_or_create_cart(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    session_id: str | None = None,
) -> Cart:

    cart = None

    if user_id:
        result = await db.execute(
            select(Cart)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images)
            )
            .where(Cart.user_id == user_id)
        )
        cart = result.scalar_one_or_none()

    elif session_id:
        result = await db.execute(
            select(Cart)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images)
            )
            .where(
                Cart.session_id == session_id,
                Cart.expires_at > datetime.now(timezone.utc),
            )
        )
        cart = result.scalar_one_or_none()

    if not cart:
        cart = Cart(
            user_id=user_id,
            session_id=session_id if not user_id else None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        db.add(cart)
        await db.commit()

        result = await db.execute(
            select(Cart)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images)
            )
            .where(Cart.id == cart.id)
        )

        cart = result.scalar_one()

    return cart


async def add_item_to_cart(
    db: AsyncSession,
    cart: Cart,
    item_in: CartItemCreate,
) -> Cart:

    result = await db.execute(
        select(ProductVariant, Inventory)
        .join(
            Inventory,
            ProductVariant.id == Inventory.variant_id,
        )
        .where(
            ProductVariant.id == item_in.variant_id,
            ProductVariant.is_active == True,
        )
    )

    row = result.first()

    if not row:
        raise ValueError("Variant not found or inactive")

    variant, inventory = row

    if inventory.quantity_available < item_in.quantity:
        raise ValueError(
            f"Only {inventory.quantity_available} items available"
        )

    existing_item = None

    for item in cart.items:
        if item.variant_id == item_in.variant_id:
            existing_item = item
            break

    if existing_item:
        new_qty = existing_item.quantity + item_in.quantity

        if inventory.quantity_available < new_qty:
            raise ValueError(
                f"Only {inventory.quantity_available} items available"
            )

        existing_item.quantity = new_qty
        existing_item.unit_price = variant.price

    else:
        new_item = CartItem(
            cart_id=cart.id,
            variant_id=item_in.variant_id,
            quantity=item_in.quantity,
            unit_price=variant.price,
        )

        db.add(new_item)

    cart.expires_at = (
        datetime.now(timezone.utc) + timedelta(days=7)
    )

    await db.commit()

    result = await db.execute(
        select(Cart)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.variant)
            .selectinload(ProductVariant.product)
            .selectinload(Product.images)
        )
        .where(Cart.id == cart.id)
    )

    return result.scalar_one()


async def update_cart_item(
    db: AsyncSession,
    cart: Cart,
    item_id: uuid.UUID,
    item_in: CartItemUpdate,
) -> Cart:

    item = None

    for i in cart.items:
        if i.id == item_id:
            item = i
            break

    if not item:
        raise ValueError("Item not found in cart")

    if item_in.quantity == 0:
        await db.delete(item)

    else:
        result = await db.execute(
            select(Inventory).where(
                Inventory.variant_id == item.variant_id
            )
        )

        inventory = result.scalar_one()

        if inventory.quantity_available < item_in.quantity:
            raise ValueError(
                f"Only {inventory.quantity_available} items available"
            )

        item.quantity = item_in.quantity
        item.unit_price = item.variant.price

    await db.commit()

    result = await db.execute(
        select(Cart)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.variant)
            .selectinload(ProductVariant.product)
            .selectinload(Product.images)
        )
        .where(Cart.id == cart.id)
    )

    return result.scalar_one()


async def merge_guest_cart_into_user_cart(
    db: AsyncSession,
    session_id: str,
    user_id: uuid.UUID,
) -> Cart:

    result = await db.execute(
        select(Cart)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.variant)
            .selectinload(ProductVariant.product)
            .selectinload(Product.images)
        )
        .where(Cart.session_id == session_id)
    )

    guest_cart = result.scalar_one_or_none()

    if not guest_cart or not guest_cart.items:
        return await get_or_create_cart(
            db,
            user_id=user_id,
        )

    user_cart = await get_or_create_cart(
        db,
        user_id=user_id,
    )

    for guest_item in guest_cart.items:

        existing = None

        for user_item in user_cart.items:
            if user_item.variant_id == guest_item.variant_id:
                existing = user_item
                break

        if existing:
            new_qty = (
                existing.quantity
                + guest_item.quantity
            )

            result = await db.execute(
                select(Inventory).where(
                    Inventory.variant_id == guest_item.variant_id
                )
            )

            inventory = result.scalar_one()

            new_qty = min(
                new_qty,
                inventory.quantity_available,
            )

            existing.quantity = new_qty
            existing.unit_price = guest_item.variant.price

        else:
            result = await db.execute(
                select(Inventory).where(
                    Inventory.variant_id == guest_item.variant_id
                )
            )

            inventory = result.scalar_one()

            new_qty = min(
                guest_item.quantity,
                inventory.quantity_available,
            )

            if new_qty > 0:
                new_item = CartItem(
                    cart_id=user_cart.id,
                    variant_id=guest_item.variant_id,
                    quantity=new_qty,
                    unit_price=guest_item.variant.price,
                )

                db.add(new_item)

    await db.delete(guest_cart)
    await db.commit()

    result = await db.execute(
        select(Cart)
        .execution_options(populate_existing=True)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.variant)
            .selectinload(ProductVariant.product)
            .selectinload(Product.images)
        )
        .where(Cart.id == user_cart.id)
    )

    return result.scalar_one()


async def clear_cart(
    db: AsyncSession,
    cart: Cart,
) -> None:

    await db.execute(
        delete(CartItem).where(
            CartItem.cart_id == cart.id
        )
    )

    await db.commit()


def build_cart_response(
    cart: Cart,
) -> CartResponse:

    items: list[CartItemResponse] = []
    subtotal = Decimal("0.00")

    for item in cart.items:

        line_total = item.unit_price * item.quantity
        subtotal += line_total

        items.append(
            CartItemResponse(
                id=item.id,
                variant_id=item.variant_id,
                product_name=item.variant.product.name,
                variant_name=(
                    f"{item.variant.product.name} - "
                    f"{item.variant.size_ml}ml"
                    if item.variant.size_ml
                    else item.variant.product.name
                ),
                sku=item.variant.sku,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=line_total,
                image_url=(
                    item.variant.product.images[0].image_url
                    if item.variant.product.images
                    else None
                ),
            )
        )

    return CartResponse(
        id=cart.id,
        items=items,
        item_count=sum(item.quantity for item in items),
        subtotal=subtotal,
        created_at=cart.created_at,
    )
    
