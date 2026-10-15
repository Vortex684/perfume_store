from fastapi import APIRouter
from app.api.v1.endpoints import (
    health, auth, products, admin_products, cart, checkout, webhooks,
    orders, admin_orders, admin_inventory,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(admin_products.router, prefix="/admin/products", tags=["admin-products"])
api_router.include_router(cart.router, prefix="/cart", tags=["cart"])
api_router.include_router(checkout.router, prefix="/checkout", tags=["checkout"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(admin_orders.router, prefix="/admin/orders", tags=["admin-orders"])
api_router.include_router(admin_inventory.router, prefix="/admin/inventory", tags=["admin-inventory"])