from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.environment import Environment
from enums.provider import Provider
from helpers.database_base import Base
from models.base import enum_type, tenant_scoped_unique
from models.identified_mixin import BigId, IdentifiedMixin
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin


class Integration(Base, IdentifiedMixin, TimestampMixin):
    """One subscription system wired to one tenant, several running side by side and reporting into the same subscriptions table."""

    __tablename__ = "integration"
    __table_args__ = (UniqueConstraint("webhook_key", name="integration_webhook_key"), tenant_scoped_unique("integration_tenant_provider", "provider"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    provider: Mapped[Provider] = mapped_column(enum_type(Provider), nullable=False)
    environment: Mapped[Environment] = mapped_column(enum_type(Environment, 16), default=Environment.PRODUCTION, nullable=False)

    # What the operator pastes into the provider console, and what tells one tenant's webhook from another's.
    webhook_key: Mapped[str] = mapped_column(String(64), nullable=False)

    # Each gateway keeps its own, named after itself, so a column never means one thing here and another there.
    revenuecat_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    revenuecat_webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant] = relationship(Tenant)

    @property
    def has_revenuecat_api_key(self) -> bool:
        return bool(self.revenuecat_api_key_encrypted)

    @property
    def has_revenuecat_webhook_secret(self) -> bool:
        return bool(self.revenuecat_webhook_secret_encrypted)

    @property
    def has_stripe_api_key(self) -> bool:
        return bool(self.stripe_api_key_encrypted)

    @property
    def has_stripe_webhook_secret(self) -> bool:
        return bool(self.stripe_webhook_secret_encrypted)
