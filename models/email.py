from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.email import OutboundEmailStatus
from helpers.db import Base
from models.base import BigId, IdentifiedMixin, TimestampMixin, UtcDateTime, enum_type
from models.tenant import Tenant


class OutboundEmail(Base, IdentifiedMixin, TimestampMixin):
    """A message written down before anything is dialled, so a mailer that is down delays it and never loses it."""

    __tablename__ = "outbound_email"
    __table_args__ = (Index("outbound_email_queue", "status", "created_at"), Index("outbound_email_tenant", "tenant_id", "created_at"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    to_address: Mapped[str] = mapped_column(String(320), nullable=False)

    # Where an answer goes when the sender is not the address that wrote it, which is what a contact form is.
    reply_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[str] = mapped_column(String(191), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    status: Mapped[OutboundEmailStatus] = mapped_column(enum_type(OutboundEmailStatus, 16), default=OutboundEmailStatus.PENDING, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    tenant: Mapped[Tenant | None] = relationship(Tenant)


class SuppressedAddress(Base, IdentifiedMixin, TimestampMixin):
    """An address a server refused for good, which nothing writes to again because sending there burns the reputation of the domain."""

    __tablename__ = "email_suppressed_address"
    __table_args__ = (UniqueConstraint("address", name="email_suppressed_address_unique"),)

    address: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
