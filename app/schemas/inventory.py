"""
Inventory schemas for admin dashboard and stock management.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.inventory_transaction import TransactionType


class InventoryResponse(BaseModel):
    """Current stock snapshot for a variant."""

    model_config = ConfigDict(from_attributes=True)

    variant_id: uuid.UUID
    product_name: str
    sku: str
    size_ml: int | None
    quantity_available: int
    quantity_reserved: int
    quantity_sold: int
    low_stock_threshold: int


class InventoryTransactionCreate(BaseModel):
    """Admin adjusts stock or records a restock."""

    variant_id: uuid.UUID
    quantity_change: int
    transaction_type: TransactionType
    reason: str | None = None


class InventoryTransactionResponse(BaseModel):
    """Audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_id: uuid.UUID
    quantity_change: int
    transaction_type: TransactionType
    reference_id: uuid.UUID | None
    reason: str | None
    created_at: datetime


class LowStockAlert(BaseModel):
    """Products running low on stock."""

    variant_id: uuid.UUID
    product_name: str
    sku: str
    quantity_available: int
    low_stock_threshold: int

