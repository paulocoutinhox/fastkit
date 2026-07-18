from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin
from fastkit_db.types import PortableJSON
from fastkit_webhooks.models.status import WebhookStatus


class WebhookEvent(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "webhook_event"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_account_id",
            "external_event_id",
            name="uq_webhook_identity",
        ),
    )

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider_account_id: Mapped[str] = mapped_column(String(120), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)

    signature_valid: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    headers: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    raw_body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default=WebhookStatus.received.value, nullable=False, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
