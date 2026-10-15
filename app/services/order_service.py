"""
Order business logic.

This handles the entire checkout flow:
1. Validate cart
2. Lock inventory (reserve items)
3. Create order with snapshot prices
4. Create payment record
5. Return checkout data

All of this happens inside a database transaction.
If any step fails, everything rolls back.
"""
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payment import PaymentStatus
from app.models.order import Order, OrderStatus, PaymentStatus as OrderPaymentStatus
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.payment import Payment, PaymentMethod
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.inventory import Inventory
from app.models.product_variant import ProductVariant
from app.schemas.order import OrderCreate
from app.services import cart_service
from app.models.inventory_transaction import (
    InventoryTransaction,
    TransactionType,
)


def generate_order_number() -> str:
    """
    Generate a human-readable order number.
    Format: LP-2026-00001 (LP = Luxe Parfum)
    In production, use a database sequence or Redis counter.
    """
    # For now, use a simple timestamp-based number
    # In production, replace with atomic counter
    now = datetime.utcnow()
    return f"LP-{now.year}-{now.strftime('%m%d%H%M%S')}"


async def create_order_from_cart(
    db: AsyncSession,
    cart: Cart,
    order_in: OrderCreate,
) -> tuple[Order, str | None]:
    """
    Convert a cart into an order.

    Steps:
    1. Calculate totals from cart items (server-side, never trust frontend)
    2. Lock inventory by reserving items
    3. Create Order row
    4. Create OrderItem rows (price snapshots)
    5. Create Payment row
    6. Log status change in history
    7. Clear cart

    Returns: (Order, client_secret) where client_secret is for Stripe only.
    """
    if not cart.items:
        raise ValueError("Cart is empty")

    # Calculate totals server-side
    subtotal = Decimal("0.00")
    for item in cart.items:
        subtotal += item.unit_price * item.quantity

    # Simple tax/shipping calculation (expand later)
    tax_rate = Decimal("0.08")  # 8% tax
    tax_total = (subtotal * tax_rate).quantize(Decimal("0.01"))
    shipping_total = Decimal("10.00") if subtotal < Decimal("100.00") else Decimal("0.00")
    grand_total = subtotal + tax_total + shipping_total

    # Create order
    order = Order(
        user_id=cart.user_id,
        order_number=generate_order_number(),
        status=OrderStatus.PENDING,
        payment_status=OrderPaymentStatus.PENDING,
        shipping_address=order_in.shipping_address,
        billing_address=order_in.billing_address or order_in.shipping_address,
        subtotal=subtotal,
        tax_total=tax_total,
        shipping_total=shipping_total,
        discount_total=Decimal("0.00"),
        grand_total=grand_total,
        currency="USD",
        notes=order_in.notes,
    )
    db.add(order)
    await db.flush()  # Get order.id without committing

    # Create order items (snapshots) and lock inventory
    for cart_item in cart.items:
        # Verify inventory still available (race condition check)
        result = await db.execute(
            select(Inventory)
            .where(Inventory.variant_id == cart_item.variant_id)
            .with_for_update()
        )
        inventory = result.scalar_one_or_none()

        if inventory is None:
            raise ValueError("Inventory record not found for this variant")

        if inventory.quantity_available < cart_item.quantity:
            raise ValueError(
                f"Insufficient stock for {cart_item.variant.product.name}. "
                f"Available: {inventory.quantity_available}, Requested: {cart_item.quantity}"
            )

        # Reserve inventory (deduct from available, add to reserved)
        inventory.quantity_available -= cart_item.quantity
        inventory.quantity_reserved += cart_item.quantity

        transaction = InventoryTransaction(
            variant_id=cart_item.variant_id,
            quantity_change=-cart_item.quantity,
            transaction_type=TransactionType.RESERVATION,
            reference_id=order.id,
            reason="Inventory reserved during checkout",
        )
        db.add(transaction)
        # Snapshot order item
        order_item = OrderItem(
            order_id=order.id,
            variant_id=cart_item.variant_id,
            product_name=cart_item.variant.product.name,
            variant_name=f"{cart_item.variant.product.name} - {cart_item.variant.size_ml}ml" if cart_item.variant.size_ml else cart_item.variant.product.name,
            sku=cart_item.variant.sku,
            quantity=cart_item.quantity,
            unit_price=cart_item.unit_price,
            total_price=cart_item.unit_price * cart_item.quantity,
        )
        db.add(order_item)

    # Create payment record
    payment_method = PaymentMethod(order_in.payment_method.lower())
    payment = Payment(
        order_id=order.id,
        payment_method=payment_method,
        amount=grand_total,
        currency="USD",
        status=PaymentStatus.PENDING
    )
    db.add(payment)

    # Log initial status
    history = OrderStatusHistory(
        order_id=order.id,
        to_status=OrderStatus.PENDING,
        reason="Order created",
    )
    db.add(history)

    # Clear cart
    await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
    for item in cart.items:
        await db.delete(item)

    await db.commit()
    
    # Refresh order with relationships for response
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
        )
        .where(Order.id == order.id)
    )
    order = result.scalar_one()
    
    # For Stripe, create PaymentIntent
    client_secret = None
    if payment_method == PaymentMethod.STRIPE:
        client_secret = await _create_stripe_payment_intent(order, grand_total)

    return order, client_secret

async def _create_stripe_payment_intent(order: Order, amount: Decimal) -> str | None:
    from app.core.config import get_settings
    settings = get_settings()
    
    # If Stripe is not configured, return None. 
    # SafePay will be added here later as an elif branch.
    if not settings.STRIPE_SECRET_KEY:
        return None
    
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    # ... rest of existing Stripe code

    # Convert Decimal dollars to cents (Stripe uses smallest currency unit)
    amount_cents = int(amount * 100)
    
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        metadata={"order_id": str(order.id), "order_number": order.order_number},
        idempotency_key=str(order.id),  # Prevent duplicate charges
    )
    
    return intent.client_secret


async def confirm_order_payment(
    db: AsyncSession,
    order: Order,
    stripe_payment_intent_id: str | None = None,
) -> Order:
    """
    Called by Stripe webhook when payment succeeds.
    Moves order from PENDING to CONFIRMED.
    Converts reserved inventory to sold inventory.
    """
    # Update order
    order.status = OrderStatus.CONFIRMED
    order.payment_status = OrderPaymentStatus.PAID
    
    # Update payment record
    if stripe_payment_intent_id:
        result = await db.execute(
            select(Payment).where(Payment.stripe_payment_intent_id == stripe_payment_intent_id)
        )
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = OrderPaymentStatus.PAID
            
    # Convert reserved inventory to sold
    result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    order_items = result.scalars().all()
    
    for item in order_items:
        result = await db.execute(
            select(Inventory).where(Inventory.variant_id == item.variant_id)
        )
        inventory = result.scalar_one()
        inventory.quantity_reserved -= item.quantity
        inventory.quantity_sold += item.quantity
        
    # Log status change
    history = OrderStatusHistory(
        order_id=order.id,
        from_status=OrderStatus.PENDING,
        to_status=OrderStatus.CONFIRMED,
        reason="Payment received via Stripe webhook",
    )
    db.add(history)

    await db.commit()
    await db.refresh(order)
    return order

async def handle_payment_failure(
    db: AsyncSession,
    order: Order,
    reason: str,
) -> Order:
    """
    Called when Stripe payment fails or is cancelled.
    Releases reserved inventory back to available stock.
    """

    order.status = OrderStatus.CANCELLED
    order.payment_status = OrderPaymentStatus.FAILED
    
    # Release reserved inventory
    result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    order_items = result.scalars().all()
    

    for item in order_items:
        result = await db.execute(
            select(Inventory).where(Inventory.variant_id == item.variant_id)
        )
        inventory = result.scalar_one()
        inventory.quantity_reserved -= item.quantity
        inventory.quantity_available += item.quantity

    # Log failure
    history = OrderStatusHistory(
        order_id=order.id,
        from_status=OrderStatus.PENDING,
        to_status=OrderStatus.CANCELLED,
        reason=f"Payment failed: {reason}",
    )
    db.add(history)

    await db.commit()
    await db.refresh(order)
    return order

async def get_order(db: AsyncSession, order_id: UUID) -> Order | None:
    """Fetch order by ID with all relationships loaded."""
    from app.repositories import order as order_repo
    return await order_repo.get_by_id(db, order_id)


async def get_user_orders(db: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 20) -> list[Order]:
    """Fetch all orders belonging to a customer."""
    from app.repositories import order as order_repo
    return await order_repo.get_by_user(db, user_id, skip, limit)


async def update_order_status(
    db: AsyncSession,
    order: Order,
    new_status: OrderStatus,
    changed_by: UUID | None = None,
    reason: str | None = None,
) -> Order:
    """
    Update order status with validation and audit logging.

    Rules:
    - Cannot change status of a CANCELLED or RETURNED order
    - Status must move forward (cannot go from SHIPPED back to PENDING)
    - Every change is logged in order_status_history
    """
    # Define valid transitions
    valid_transitions = {
        OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
        OrderStatus.CONFIRMED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
        OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
        OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
        OrderStatus.DELIVERED: [OrderStatus.RETURNED],
        OrderStatus.RETURNED: [],  # Terminal state
        OrderStatus.CANCELLED: [],  # Terminal state
    }

    if order.status in (OrderStatus.CANCELLED, OrderStatus.RETURNED):
        raise ValueError(f"Cannot modify a {order.status.value} order")

    allowed = valid_transitions.get(order.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Invalid status transition: {order.status.value} → {new_status.value}. "
            f"Allowed: {[s.value for s in allowed]}"
        )

    old_status = order.status
    order.status = new_status

    # Log the change
    history = OrderStatusHistory(
        order_id=order.id,
        from_status=old_status.value,
        to_status=new_status.value,
        changed_by=changed_by,
        reason=reason or f"Status changed from {old_status.value} to {new_status.value}",
    )
    db.add(history)

    await db.commit()
    await db.refresh(order)
    return order


async def cancel_order(
    db: AsyncSession,
    order: Order,
    changed_by: UUID | None = None,
    reason: str | None = None,
) -> Order:
    """
    Cancel an order and release any reserved inventory.
    Only allowed if order is not already shipped/delivered.
    """
    if order.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.RETURNED):
        raise ValueError("Cannot cancel an order that has already been shipped or delivered")

    old_status = order.status
    order.status = OrderStatus.CANCELLED
    order.payment_status = OrderPaymentStatus.FAILED

    # Release reserved inventory back to available
    result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    items = result.scalars().all()

    for item in items:
        result = await db.execute(
            select(Inventory).where(Inventory.variant_id == item.variant_id)
        )
        inventory = result.scalar_one_or_none()

    # Only release if it was reserved (not yet sold)
        if inventory is None:
            raise ValueError(
                f"Inventory not found for variant {item.variant_id}"
            )

        if inventory.quantity_reserved < item.quantity:
            raise ValueError(
                f"Insufficient reserved stock for variant {item.variant_id}"
            )

        inventory.quantity_reserved -= item.quantity
        inventory.quantity_available += item.quantity

        transaction = InventoryTransaction(
            variant_id=item.variant_id,
            quantity_change=item.quantity,
            transaction_type=TransactionType.RESERVATION,
            reference_id=order.id,
            changed_by=changed_by,
            reason="Reserved inventory released after order cancellation",
        )
        db.add(transaction)  
        
    # Log cancellation
    history = OrderStatusHistory(
        order_id=order.id,
        from_status=old_status.value if old_status else None,
        to_status=OrderStatus.CANCELLED.value,
        changed_by=changed_by,
        reason=reason or "Order cancelled",
    )
    db.add(history)

    await db.commit()
    await db.refresh(order)
    return order


async def mark_cod_payment_collected(
    db: AsyncSession,
    order: Order,
    changed_by: UUID,
) -> Order:
    """
    Admin marks a COD order as paid after collecting cash on delivery.
    """
    if order.payment_status == OrderPaymentStatus.PAID:
        raise ValueError("Order is already marked as paid")

    order.payment_status = OrderPaymentStatus.PAID

    history = OrderStatusHistory(
        order_id=order.id,
        from_status=order.status.value,
        to_status=order.status.value,
        changed_by=changed_by,
        reason="COD payment collected",
    )
    db.add(history)

    await db.commit()
    await db.refresh(order)
    return order