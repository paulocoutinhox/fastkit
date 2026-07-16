from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, TimestampMixin, PrimaryKeyMixin
from fastkit_db.types import PortableJSON


class DeliveryStatus(str, Enum):
    pending = "pending"
    queued = "queued"
    sending = "sending"
    sent = "sent"
    retrying = "retrying"
    failed = "failed"
    cancelled = "cancelled"


class EmailDelivery(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "email_deliveries"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    template_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    template_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locale: Mapped[str] = mapped_column(String(12), default="en", nullable=False)

    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to: Mapped[list] = mapped_column(PortableJSON, nullable=False)
    cc: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)
    bcc: Mapped[list | None] = mapped_column(PortableJSON, nullable=True)

    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default=DeliveryStatus.pending.value, nullable=False, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
