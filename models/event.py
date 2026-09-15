from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.event import AppEventStatus
from helpers.db import Base
from models.base import BigId, IdentifiedMixin, TimestampMixin, UtcDateTime, enum_type
from models.tenant import Tenant
from models.user import User


class AppEvent(Base, IdentifiedMixin, TimestampMixin):
    """Something the app reported, carrying the client UUID so a retried batch lands once."""

    __tablename__ = "app_event"
    __table_args__ = (UniqueConstraint("uuid", name="app_event_uuid"), Index("app_event_name", "name"), Index("app_event_status_queue", "status", "occurred_at"), Index("app_event_tenant", "tenant_id", "occurred_at"), Index("app_event_user", "user_id", "occurred_at"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=True)

    uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    status: Mapped[AppEventStatus] = mapped_column(enum_type(AppEventStatus, 16), default=AppEventStatus.PENDING, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
    user: Mapped[User | None] = relationship(User)
