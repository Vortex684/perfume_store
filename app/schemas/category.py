import uuid
from datetime import datetime

from pydantic import BaseModel,ConfigDict

from app.models.category import GenderTarget



class CategoryBase(BaseModel):
    name: str
    slug: str
    description: str | None = None
    gender_target: GenderTarget | None = None
    is_active: bool = True
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    parent_id: uuid.UUID | None = None


class CategoryResponse(CategoryBase):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)