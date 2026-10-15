"""Business rules for return requests, inventory restocking, and COD refunds.

Important launch rule:
This service makes NO Stripe, SafePay, or other payment-gateway calls.
COD refunds are manual. A refund stays PENDING until an admin confirms
that the real transfer has occurred.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Inventory
from app.models.inventory_transaction import (
    InventoryTransaction,
    TransactionType,
)
from app.models.order import Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.order_status_history import OrderStatusHistory
from app.models.refund import Refund, RefundStatus
from app.models.return_item import ReturnItem
from app.models.return_request import ReturnRequest, ReturnStatus
from app.schemas.returns import ReturnRequestCreate


# These statuses count against the purchased quantity.
# A rejected request does not count, so the customer can submit a new request.
_RETURN_STATUSES_THAT_COUNT = (
    ReturnStatus.REQUESTED,
    ReturnStatus.APPROVED, 
    ReturnStatus.ITEMS_RECEIVED,
    ReturnStatus.REFUNDED,
)


async def _get_locked_return_request(
    db: AsyncSession,
    return_id: UUID,
) -> ReturnRequest | None:
    """Lock a return row to help prevent concurrent admin actions."""
    result = await db.execute(
        select(ReturnRequest)
        .where(ReturnRequest.id == return_id)
        .with_for_update()
    )

    return result.scalar_one_or_none()


async def _get_delivery_timestamp(
    db: AsyncSession,
    order_id: UUID,
):
    """Find when the order was marked delivered in its status history.

    There is no dedicated delivered_at column assumed here, so the audit
    history is used. If the delivery event is missing, fail safely rather
    than incorrectly calculating the return window from order creation.
    """
    result = await db.execute(
        select(OrderStatusHistory.created_at)
        .where(
            OrderStatusHistory.order_id == order_id,
            OrderStatusHistory.to_status.in_(
                [
                    OrderStatus.DELIVERED.value,
                    OrderStatus.DELIVERED.name,
                ]
            ),
        )
        .order_by(OrderStatusHistory.created_at.desc())
        .limit(1)
    )

    return result.scalar_one_or_none()


async def create_return_request(
    db: AsyncSession,
    user_id: UUID,
    obj_in: ReturnRequestCreate,
) -> ReturnRequest:
    """Create a return for a delivered order within the 14-day policy."""

    if not obj_in.items:
        raise ValueError("At least one order item must be included")

    # Lock the customer's order before checking existing return quantities.
    # Concurrent requests for the same order will serialize on PostgreSQL.
    result = await db.execute(
        select(Order)
        .where(
            Order.id == obj_in.order_id,
            Order.user_id == user_id,
        )
        .with_for_update()
    )

    order = result.scalar_one_or_none()

    if order is None:
        # Do not reveal whether another customer's order exists.
        raise ValueError("Order not found")

    # The policy only permits returns after the order has been delivered.
    if order.status != OrderStatus.DELIVERED:
        raise ValueError("Only delivered orders can be returned")

    delivered_at = await _get_delivery_timestamp(db, order.id)

    if delivered_at is None:
        # Do not silently substitute the order's creation time.
        raise ValueError(
            "Delivery timestamp is missing; contact support"
        )

    # The 14-day window starts at recorded delivery time.
    now = datetime.now(timezone.utc)

    # Handle legacy timestamps that were stored without timezone information.
    if delivered_at.tzinfo is None:
        delivered_at = delivered_at.replace(tzinfo=timezone.utc)

    if now > delivered_at + timedelta(days=14):
        raise ValueError(
            "Returns must be requested within 14 days of delivery"
        )

    # Reject duplicate order-item IDs in one request.
    # Otherwise clients could split quantities across duplicate lines.
    requested_by_item: dict[UUID, int] = {}
    customer_condition_by_item: dict[UUID, str | None] = {}

    for item_in in obj_in.items:
        if item_in.order_item_id in requested_by_item:
            raise ValueError(
                "Each order item may appear only once in a return request"
            )

        requested_by_item[item_in.order_item_id] = item_in.quantity
        customer_condition_by_item[
            item_in.order_item_id
        ] = item_in.customer_condition

    # Fetch only items that belong to this order.
    order_items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )

    order_items = {
        item.id: item
        for item in order_items_result.scalars().all()
    }

    # Add up quantities in existing non-rejected return requests.
    # REQUESTED counts too, preventing overlapping pending requests.
    previous_result = await db.execute(
        select(
            ReturnItem.order_item_id,
            func.sum(ReturnItem.quantity),
        )
        .join(
            ReturnRequest,
            ReturnRequest.id == ReturnItem.return_request_id,
        )
        .where(
            ReturnRequest.order_id == order.id,
            ReturnRequest.status.in_(
                _RETURN_STATUSES_THAT_COUNT
            ),
        )
        .group_by(ReturnItem.order_item_id)
    )

    previously_requested = {
        item_id: int(quantity or 0)
        for item_id, quantity in previous_result.all()
    }

    # Validate every requested line against its original purchased quantity.
    for order_item_id, new_quantity in requested_by_item.items():
        order_item = order_items.get(order_item_id)

        if order_item is None:
            raise ValueError(
                f"Order item {order_item_id} does not belong to this order"
            )

        already_requested = previously_requested.get(
            order_item_id,
            0,
        )

        remaining = order_item.quantity - already_requested

        if new_quantity > remaining:
            raise ValueError(
                f"Cannot return {new_quantity} of "
                f"{order_item.product_name}. "
                f"Purchased: {order_item.quantity}; "
                f"already requested: {already_requested}; "
                f"remaining: {max(remaining, 0)}"
            )

    # Create the return request and its lines in one transaction.
    return_req = ReturnRequest(
        order_id=order.id,
        user_id=user_id,
        reason=obj_in.reason,
        customer_notes=obj_in.customer_notes,
        status=ReturnStatus.REQUESTED,
    )

    db.add(return_req)
    await db.flush()  # Generate the parent's ID before creating child rows.

    for order_item_id, quantity in requested_by_item.items():
        db.add(
            ReturnItem(
                return_request_id=return_req.id,
                order_item_id=order_item_id,
                quantity=quantity,

                # Actual condition is unknown until admin inspection.
                condition="pending_inspection",

                # Store the customer's report for reference only.
                customer_condition=customer_condition_by_item[
                    order_item_id
                ],
            )
        )

    try:
        await db.commit()
    except Exception:
        # Keep the parent and child records from being partially committed.
        await db.rollback()
        raise

    # Re-query relationships eagerly so response serialization does not
    # accidentally trigger asynchronous lazy loading.
    result = await db.execute(
        select(ReturnRequest)
        .options(
            selectinload(ReturnRequest.items).selectinload(
                ReturnItem.order_item
            ),
            selectinload(ReturnRequest.refund),
        )
        .where(ReturnRequest.id == return_req.id)
        .execution_options(populate_existing=True)
    )

    return result.scalar_one()

async def update_return_status(
    db: AsyncSession,
    return_id: UUID,
    new_status: ReturnStatus,
    admin_id: UUID,
    admin_notes: str | None = None,
    received_conditions: dict[UUID, str] | None = None,
) -> ReturnRequest:
    """Apply allowed admin transitions and restock eligible returned items."""
    
    return_req = await _get_locked_return_request(db, return_id)

    if return_req is None:
        raise ValueError("Return request not found")

    # Only the transitions defined here are allowed.
    # REFUNDED is handled separately by the refund-confirmation function.
    
    valid_transitions = {
        ReturnStatus.REQUESTED: {
            ReturnStatus.APPROVED,
            ReturnStatus.REJECTED,
        },
        ReturnStatus.APPROVED: {
            ReturnStatus.ITEMS_RECEIVED,
        },
    }

    if new_status not in valid_transitions.get(
        return_req.status,
        set(),
    ):
        raise ValueError(
            f"Cannot transition from {return_req.status.value} "
            f"to {new_status.value}"
        )
    
    # Load return lines and original order-item snapshots before stock changes.
    result = await db.execute(
        select(ReturnItem)
        .options(selectinload(ReturnItem.order_item))
        .where(ReturnItem.return_request_id == return_req.id)
    )

    return_items = list(result.scalars().all())
    
    if new_status == ReturnStatus.ITEMS_RECEIVED:
        # The admin must inspect every returned line, with no missing or
        # unexpected IDs. Customer-reported condition is not sufficient.
        expected_item_ids = {
            item.order_item_id
            for item in return_items
        }
        
        supplied_item_ids = set(
            (received_conditions or {}).keys()
        )

        if supplied_item_ids != expected_item_ids:
            raise ValueError(
                "When marking items received, provide the inspected "
                "condition for every returned item"
            )

        for return_item in return_items:
            order_item = return_item.order_item

            # Record the condition the admin actually inspected.
            return_item.condition = (
                received_conditions or {}
            )[return_item.order_item_id]
            
            # Only unopened items are added back to sellable stock.
            # Items without a variant cannot be safely matched to inventory.
            if (
                return_item.condition != "unopened"
                or order_item.variant_id is None
            ):
                continue

            # Lock the inventory row to reduce concurrent stock-update issues.
            inv_result = await db.execute(
                select(Inventory)
                .where(
                    Inventory.variant_id == order_item.variant_id
                )
                .with_for_update()
            )

            inventory = inv_result.scalar_one_or_none()
            
            if inventory is None:
                # Never invent an inventory record automatically.
                # Roll back earlier stock changes from this same transaction.
                await db.rollback()

                raise ValueError(
                    f"Inventory record missing for SKU {order_item.sku}; "
                    "cannot receive this return until inventory is fixed"
                )

            # Restore the returned quantity to available stock.
            inventory.quantity_available += return_item.quantity
            
            # Record the stock movement for auditing.
            db.add(
                InventoryTransaction(
                    variant_id=order_item.variant_id,
                    quantity_change=return_item.quantity,
                    transaction_type=TransactionType.RETURN,
                    reference_id=return_req.order_id,
                    reason=(
                        "Unopened item restocked from return "
                        f"{return_req.id}"
                    ),
                )
            )

    # Save the requested status and optional internal admin notes.
    return_req.status = new_status

    if admin_notes is not None:
        return_req.admin_notes = admin_notes

    # InventoryTransaction records and admin notes provide the current audit
    # trail here; this implementation does not add a separate return-history table.
    
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    
    # Refresh relationships after commit for safe response serialization.
    result = await db.execute(
        select(ReturnRequest)
        .options(
            selectinload(ReturnRequest.items).selectinload(
                ReturnItem.order_item
            ),
            selectinload(ReturnRequest.refund),
        )
        .where(ReturnRequest.id == return_req.id)
        .execution_options(populate_existing=True)
    )

    return result.scalar_one()