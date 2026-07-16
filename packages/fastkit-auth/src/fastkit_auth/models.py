from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, TimestampMixin, PrimaryKeyMixin


class SessionStatus(str, Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


class Session(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "sessions"

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    identity_tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.active.value, nullable=False)

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
