import uuid

from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class ProductFragranceNote(Base):
    __tablename__ = "product_fragrance_notes"
    
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"),primary_key=True)
    fragrance_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fragrance_notes.id", ondelete="CASCADE"), primary_key=True
    )
    
    product: Mapped["Product"] = relationship("Product", back_populates="fragrance_notes")
    fragrance_note: Mapped["FragranceNote"] = relationship("FragranceNote", back_populates="product_links")