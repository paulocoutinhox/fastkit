from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin


class Subcategory(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "demo_subcategory"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("demo_category.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def display_label(self) -> str:
        return self.name
