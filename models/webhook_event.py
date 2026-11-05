from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.normalized_action import NormalizedAction
from enums.webhook_event_status import WebhookEventStatus
from helpers.database_base import Base
from models.base import Money, enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.integration import Integration
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin
from models.utc_date_time import UtcDateTime


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
