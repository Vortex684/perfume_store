import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict

from app.models.product import ProductGender


class ProductVariantBase(BaseModel):
    sku: str
    size_ml: int | None = None
    price: Decimal
    compare_at_price: Decimal | None = None
    cost_price: Decimal | None = None
    is_active: bool = True


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantResponse(ProductVariantBase):
    id: uuid.UUID
    product_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class ProductImageBase(BaseModel):
    image_url: str
    alt_text: str | None = None
    sort_order: int = 0
    variant_id: uuid.UUID | None = None


class ProductImageCreate(ProductImageBase):
    pass


class ProductImageResponse(ProductImageBase):
    id: uuid.UUID
    product_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class FragranceNoteLink(BaseModel):
    fragrance_note_id: uuid.UUID


class ProductBase(BaseModel):
    name: str
    slug: str
    description: str | None = None
    story: str | None = None
    base_price: Decimal
    gender: ProductGender
    is_active: bool = True
    is_featured: bool = False


class ProductCreate(ProductBase):
    brand_id: uuid.UUID
    category_id: uuid.UUID
    variants: list[ProductVariantCreate] = Field(default_factory=list)
    images: list[ProductImageCreate] = Field(default_factory=list)
    fragrance_note_ids: list[uuid.UUID] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    story: str | None = None
    base_price: Decimal | None = None
    gender: ProductGender | None = None
    brand_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    is_active: bool | None = None
    is_featured: bool | None = None


class ProductResponse(ProductBase):
    id: uuid.UUID
    brand_id: uuid.UUID
    category_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    variants: list[ProductVariantResponse]
    images: list[ProductImageResponse]

    model_config = ConfigDict(from_attributes=True)


class ProductListItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    base_price: Decimal
    gender: ProductGender
    is_active: bool
    brand_name: str
    category_name: str
    primary_image_url: str | None = None

    model_config = ConfigDict(from_attributes=True)