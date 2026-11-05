from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.purchase_status import PurchaseStatus
from helpers.database_base import Base
from models.base import Money, enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.product import Product
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin
from models.user import User
from models.utc_date_time import UtcDateTime


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
