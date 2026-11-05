from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from helpers.search import search_index
from models.base import tenant_scoped_unique
from models.identified_mixin import BigId, IdentifiedMixin
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin


class Entitlement(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "subscription_entitlement"
    __table_args__ = (tenant_scoped_unique("subscription_entitlement_tenant_code", "code"), Index("subscription_entitlement_order", "tenant_id", "name"), search_index("subscription_entitlement_search", "name"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
