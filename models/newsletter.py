from datetime import datetime
from uuid import uuid4

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.newsletter import NewsletterStatus
from helpers.db import Base
from models.base import BigId, IdentifiedMixin, TimestampMixin, UtcDateTime, enum_type, tenant_scoped_unique
from models.tenant import Tenant


class NewsletterSubscription(Base, IdentifiedMixin, TimestampMixin):
    """One address that asked to hear from one brand, which is only ever written to once the address itself confirmed it."""

    __tablename__ = "newsletter_subscription"
    __table_args__ = (tenant_scoped_unique("newsletter_subscription_email", "email"), UniqueConstraint("token", name="newsletter_subscription_token"), Index("newsletter_subscription_listing", "tenant_id", "status", "created_at"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)

    # The link of the confirmation and the one of the goodbye are the same secret, because both are the address proving it is the address.
    token: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()), nullable=False)

    status: Mapped[NewsletterStatus] = mapped_column(enum_type(NewsletterStatus, 16), default=NewsletterStatus.PENDING, nullable=False)

    # When this address was last written to, because a form anybody can send is otherwise a way to mail somebody who never asked.
    invited_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    tenant: Mapped[Tenant] = relationship(Tenant)
