from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin
from fastkit_db.types import PortableJSON


class Showcase(PrimaryKeyMixin, TimestampMixin, Base):
    """Exercises every admin field type in a single entity."""

    __tablename__ = "demo_showcase"

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    tags: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)
    brand_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    release_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attributes: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reference_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
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

    def display_label(self) -> str:
        return self.title
