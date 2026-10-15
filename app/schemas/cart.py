import uuid
from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CartItemBase(BaseModel):
    variant_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=99)


class CartItemCreate(CartItemBase):
    pass


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=0, le=99)


class CartItemResponse(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    product_name: str
    variant_name: str
    sku: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    image_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    id: uuid.UUID
    items: list[CartItemResponse]
    item_count: int
    subtotal: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)