from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.product import ProductResponse, ProductListItem
from app.services import product_service
from app.repositories import product as product_repo

router = APIRouter()


@router.get("", response_model=list[ProductListItem])
async def list_products(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    gender: str | None = None,
    category_id: UUID | None = None,
    brand_id: UUID | None = None,
):
    products, total = await product_repo.get_multi(
        db, skip=skip, limit=limit, gender=gender, category_id=category_id, brand_id=brand_id
    )
    
    # Convert to lightweight response
    result = []
    for p in products:
        primary_image = p.images[0].image_url if p.images else None
        result.append(ProductListItem(
            id=p.id,
            name=p.name,
            slug=p.slug,
            base_price=p.base_price,
            gender=p.gender,
            is_active=p.is_active,
            brand_name=p.brand.name,
            category_name=p.category.name,
            primary_image_url=primary_image,
        ))
    return result

@router.get('/{slug}',response_model=ProductResponse)
async def get_product(slug: str , db: AsyncSession = Depends(get_db)):
    product = await product_repo.get_by_slug(db, slug=slug)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product