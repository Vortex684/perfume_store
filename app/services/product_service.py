from uuid import UUID
from slugify import slugify 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.product_image import ProductImage
from app.models.product_fragrance_note import ProductFragranceNote
from app.models.inventory import Inventory
from app.schemas.product import ProductCreate, ProductUpdate, ProductVariantCreate, ProductImageCreate

from app.repositories import product as product_repo
from app.repositories import brand as brand_repo
from app.repositories import category as category_repo


async def create_product(db: AsyncSession, obj_in: ProductCreate) -> Product:
    # Validate brand and category exist
    brand = await brand_repo.get_by_id(db, obj_in.brand_id)
    if not brand:
        raise ValueError("Brand not found")

    category = await category_repo.get_by_id(db, obj_in.category_id)
    if not category:
        raise ValueError("Category not found")

    db_product = Product(
        name=obj_in.name,
        slug=obj_in.slug or slugify(obj_in.name),
        description=obj_in.description,
        story=obj_in.story,
        base_price=obj_in.base_price,
        gender=obj_in.gender,
        brand_id=obj_in.brand_id,
        category_id=obj_in.category_id,
        is_active=obj_in.is_active,
        is_featured=obj_in.is_featured,
    )

    db.add(db_product)
    await db.flush()  # Get db_product.id without committing

    # Create variants + inventory
    for variant_in in obj_in.variants:
        db_variant = ProductVariant(
            product_id=db_product.id,
            sku=variant_in.sku,
            size_ml=variant_in.size_ml,
            price=variant_in.price,
            compare_at_price=variant_in.compare_at_price,
            cost_price=variant_in.cost_price,
            is_active=variant_in.is_active,
        )

        db.add(db_variant)
        await db.flush()  # Get db_variant.id

        # Every variant gets its own inventory row
        db_inventory = Inventory(
            variant_id=db_variant.id
        )
        db.add(db_inventory)

    # Create images
    for image_in in obj_in.images:
        db_image = ProductImage(
            product_id=db_product.id,
            variant_id=image_in.variant_id,
            image_url=image_in.image_url,
            alt_text=image_in.alt_text or obj_in.name,
            sort_order=image_in.sort_order,
        )
        db.add(db_image)

    # Link fragrance notes
    for note_id in obj_in.fragrance_note_ids:
        db_link = ProductFragranceNote(
            product_id=db_product.id,
            fragrance_note_id=note_id
        )
        db.add(db_link)

    await db.commit()

    # Reload product with relationships needed by ProductResponse.
    # This prevents async lazy-loading / MissingGreenlet errors.
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.brand),
            selectinload(Product.category),
        )
        .where(Product.id == db_product.id)
    )

    return result.scalar_one()


async def update_product(
    db: AsyncSession,
    product: Product,
    obj_in: ProductUpdate
) -> Product:

    update_data = obj_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)

    return product


async def archive_product(
    db: AsyncSession,
    product: Product
) -> Product:
    """Soft delete: set is_active=False. Preserves order history."""

    product.is_active = False

    await db.commit()
    await db.refresh(product)

    return product