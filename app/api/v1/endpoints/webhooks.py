"""
Stripe webhook endpoint.

This is the ONLY place where we trust payment confirmation.
The frontend "success" callback is unreliable. This endpoint is called
directly by Stripe's servers with cryptographic proof of payment.

Security:
- We verify the Stripe-Signature header using our webhook secret.
- If verification fails, we return 400 and ignore the request.
- We handle idempotency: if we already processed this payment_intent, we ignore duplicates.
"""
import stripe
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.config import get_settings
from app.models.order import Order
from app.models.payment import Payment
from app.services import order_service

settings = get_settings()
router = APIRouter()

# If Stripe is not configured, create an empty router so the app still starts
if not settings.STRIPE_SECRET_KEY:
    router = APIRouter()
    
    @router.post("/stripe")
    async def stripe_disabled():
        return {"message": "Stripe is not configured"}
else:
    
    router = APIRouter()
    @router.post("/stripe")
    async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
        """
        Handle Stripe webhooks.

        Events we care about:
        - payment_intent.succeeded: Payment confirmed, fulfill order
        - payment_intent.payment_failed: Payment failed, release inventory
        """
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            # Invalid payload
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Handle the event
        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            await _handle_payment_success(db, payment_intent)

        elif event["type"] == "payment_intent.payment_failed":
            payment_intent = event["data"]["object"]
            await _handle_payment_failure(db, payment_intent)

        # Return 200 to Stripe so they stop retrying
        return {"status": "success"}


    async def _handle_payment_success(db: AsyncSession, payment_intent: dict):
        """
        Payment succeeded. Find the order and confirm it.
        """
        order_id = payment_intent.get("metadata", {}).get("order_id")
        if not order_id:
            raise HTTPException(status_code=400, detail="Missing order_id in metadata")

        # Check for duplicate handling (idempotency)
        result = await db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == payment_intent["id"],
                Payment.status == "succeeded",
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            # Already processed, return success
            return

        # Find order
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Confirm order
        await order_service.confirm_order_payment(db, order, payment_intent["id"])


    async def _handle_payment_failure(db: AsyncSession, payment_intent: dict):
        """
        Payment failed. Release reserved inventory.
        """
        order_id = payment_intent.get("metadata", {}).get("order_id")
        if not order_id:
            raise HTTPException(status_code=400, detail="Missing order_id in metadata")

        result = await db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        failure_message = payment_intent.get("last_payment_error", {}).get("message", "Unknown error")
        await order_service.handle_payment_failure(db, order, failure_message)