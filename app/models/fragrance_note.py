from enum import Enum as PyEnum

from sqlalchemy import String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class NoteType(str, PyEnum):
    TOP = "top"
    HEART = "heart"
    BASE = "base"


class FragranceNote(BaseModel):
    __tablename__ = "fragrance_notes"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    note_type: Mapped[NoteType] = mapped_column(Enum(NoteType), nullable=False)

    product_links: Mapped[list["ProductFragranceNote"]] = relationship("ProductFragranceNote", back_populates="fragrance_note")