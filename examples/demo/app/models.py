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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fastkit_db.base import Base, TimestampMixin, PrimaryKeyMixin
from fastkit_db.types import PortableJSON


class Category(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "demo_category"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def display_label(self) -> str:
        return self.name


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


class Survey(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "demo_survey"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def display_label(self) -> str:
        return self.name


class SurveyQuestion(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "demo_survey_question"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    survey_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("demo_survey.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    def display_label(self) -> str:
        return self.name


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


class GeoSample(PrimaryKeyMixin, TimestampMixin, Base):
    """Exercises triple dependent country→state→city selects and lookups with slow remote options."""

    __tablename__ = "demo_geo"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sel_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sel_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sel_city: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sel_district: Mapped[str | None] = mapped_column(String(8), nullable=True)
    look_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    look_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    look_city: Mapped[str | None] = mapped_column(String(8), nullable=True)
    look_district: Mapped[str | None] = mapped_column(String(8), nullable=True)

    def display_label(self) -> str:
        return self.name


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
