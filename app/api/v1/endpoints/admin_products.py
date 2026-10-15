from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_db, require_admin
from app.models.user import User
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.repositories import product as product_repo
from app.services import product_service

router = APIRouter()


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    obj_in: ProductCreate,
    db = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = await product_service.create_product(db, obj_in)
    return product


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    obj_in: ProductUpdate,
    db = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = await product_repo.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    updated = await product_service.update_product(db, product, obj_in)
    return updated


@router.delete("/{product_id}")
async def archive_product(
    product_id: UUID,
    db = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = await product_repo.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await product_service.archive_product(db, product)
    return {"message": "Product archived"}