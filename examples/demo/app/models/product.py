from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin


class Product(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "demo_product"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sku: Mapped[str] = mapped_column(String(40), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    category_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("demo_category.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subcategory_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("demo_subcategory.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category: Mapped["Category | None"] = relationship(lazy="raise")
    subcategory: Mapped["Subcategory | None"] = relationship(lazy="raise")

    def display_label(self) -> str:
        return self.name
