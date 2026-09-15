from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.commerce import PurchaseStatus
from helpers.dates import now
from helpers.db import Base
from helpers.search import search_index
from models.account import Currency
from models.base import AddressedMixin, BigId, IdentifiedMixin, Money, TimestampMixin, UtcDateTime, enum_type, tenant_scoped_unique
from models.tenant import Tenant
from models.user import User


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


class Purchase(Base, IdentifiedMixin, TimestampMixin):
    """One payment for one product, written on this side before the buyer is ever sent to a gateway."""

    __tablename__ = "commerce_purchase"
    __table_args__ = (UniqueConstraint("reference", name="commerce_purchase_reference"), UniqueConstraint("integration_id", "external_id", name="commerce_purchase_integration_external"), Index("commerce_purchase_owner", "user_id", "created_at"), Index("commerce_purchase_tenant_status", "tenant_id", "status"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigId, ForeignKey("commerce_product.id", ondelete="RESTRICT"), nullable=False)
    integration_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("integration.id", ondelete="RESTRICT"), nullable=True)

    # Minted before the buyer leaves, because what a gateway echoes back has to name a row it never saw being written.
    reference: Mapped[str] = mapped_column(String(64), default=lambda: f"purchase-{uuid4()}", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(191), nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price: Mapped[Decimal] = mapped_column(Money, nullable=False)

    status: Mapped[PurchaseStatus] = mapped_column(enum_type(PurchaseStatus, 16), default=PurchaseStatus.PENDING, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant] = relationship(Tenant)
    user: Mapped[User] = relationship(User)
    product: Mapped[Product] = relationship(Product)


class UserProduct(Base, IdentifiedMixin, TimestampMixin):
    """What the account owns for good, however it got there, because nothing here ever takes one back."""

    __tablename__ = "user_product"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="user_product_unique"), Index("user_product_owned", "user_id", "granted_at"))

    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigId, ForeignKey("commerce_product.id", ondelete="RESTRICT"), nullable=False)
    purchase_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("commerce_purchase.id", ondelete="SET NULL"), nullable=True)
    subscription_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("subscription.id", ondelete="SET NULL"), nullable=True)
    benefit_grant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("subscription_benefit_grant.id", ondelete="SET NULL"), nullable=True)

    granted_at: Mapped[datetime] = mapped_column(UtcDateTime, default=now, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    user: Mapped[User] = relationship(User)
    product: Mapped[Product] = relationship(Product)
