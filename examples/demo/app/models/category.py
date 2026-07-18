from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin


class Category(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "demo_category"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def display_label(self) -> str:
        return self.name
