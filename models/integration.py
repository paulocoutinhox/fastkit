from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.integration import Environment, NormalizedAction, Provider, WebhookEventStatus
from helpers.db import Base
from helpers.search import search_index
from models.base import BigId, IdentifiedMixin, Money, TimestampMixin, UtcDateTime, enum_type, tenant_scoped_unique
from models.subscription import Plan
from models.tenant import Tenant


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


class ExternalProduct(Base, IdentifiedMixin, TimestampMixin):
    """What a plan is sold as inside one provider, where the price is a reference and not what a buyer pays."""

    __tablename__ = "integration_external_product"
    __table_args__ = (UniqueConstraint("integration_id", "external_id", name="integration_external_product_ext"), search_index("integration_external_product_search", "display_name"))

    integration_id: Mapped[int] = mapped_column(BigId, ForeignKey("integration.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_plan.id", ondelete="RESTRICT"), nullable=False)

    external_id: Mapped[str] = mapped_column(String(191), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reference_price: Mapped[Decimal | None] = mapped_column(Money, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    integration: Mapped[Integration] = relationship(Integration)
    plan: Mapped[Plan] = relationship(Plan)


class WebhookEvent(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "integration_webhook_event"
    __table_args__ = (
        UniqueConstraint("integration_id", "external_event_id", name="integration_webhook_event_ext"),
        Index("integration_webhook_event_status", "status", "created_at"),
        Index("integration_webhook_event_created", "tenant_id", "created_at"),
        Index("integration_webhook_event_occurred", "subscription_id", "occurred_at"),
    )

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE", name="integration_webhook_event_tenant"), nullable=True)
    integration_id: Mapped[int] = mapped_column(BigId, ForeignKey("integration.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    subscription_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("subscription.id", ondelete="SET NULL"), nullable=True)

    external_event_id: Mapped[str] = mapped_column(String(191), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # The name the gateway gave it stays in `payload`, and what this side acts on is the action it became.
    action: Mapped[NormalizedAction | None] = mapped_column(enum_type(NormalizedAction), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    occurred_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    status: Mapped[WebhookEventStatus] = mapped_column(enum_type(WebhookEventStatus, 16), default=WebhookEventStatus.RECEIVED, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant] = relationship(Tenant)
    integration: Mapped[Integration] = relationship(Integration)
