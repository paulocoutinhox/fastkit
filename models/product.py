from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from helpers.search import search_index
from models.addressed_mixin import AddressedMixin
from models.base import Money, tenant_scoped_unique
from models.currency import Currency
from models.identified_mixin import BigId, IdentifiedMixin
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin


class Product(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    """Something bought once and owned for good, which a plan may also hand over as a benefit."""

    __tablename__ = "commerce_product"
    __table_args__ = (UniqueConstraint("uuid", name="commerce_product_uuid"), tenant_scoped_unique("commerce_product_slug", "slug"), Index("commerce_product_listing", "tenant_id", "active", "position"), search_index("commerce_product_search", "name"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # What owning it lets the account download, which only somebody who owns it is ever handed an address for.
    file: Mapped[str | None] = mapped_column(String(512), nullable=True)

    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    price: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)

    # What owning it puts in a balance, applied the same way whether it was bought or handed over by a plan.
    credits: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    credits_currency_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("currency.id", ondelete="RESTRICT"), nullable=True)

    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
    credits_currency: Mapped[Currency | None] = relationship(Currency)
