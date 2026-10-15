import uuid
from datetime import datetime

from pydantic import BaseModel


class BrandBase(BaseModel):
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None
    is_active: bool = True


class BrandCreate(BrandBase):
    pass


class BrandResponse(BrandBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True