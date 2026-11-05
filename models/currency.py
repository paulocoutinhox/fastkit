from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from helpers.search import search_index
from models.addressed_mixin import AddressedMixin
from models.base import tenant_scoped_unique
from models.identified_mixin import BigId, IdentifiedMixin
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin


class Currency(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    """A unit an account holds a balance in, which is whatever the product decides to call it and never a fixed pair."""

    __tablename__ = "currency"
    __table_args__ = (UniqueConstraint("uuid", name="currency_uuid"), tenant_scoped_unique("currency_code", "code"), Index("currency_listing", "tenant_id", "active", "position"), search_index("currency_search", "name"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(8), nullable=True)

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
