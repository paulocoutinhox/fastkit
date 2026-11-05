from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from enums.authentication_surface import AuthenticationSurface
from helpers.database_base import Base
from models.base import enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.utc_date_time import UtcDateTime


class EmailLoginChallenge(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "email_login_challenge"
    __table_args__ = (Index("email_login_challenge_scope", "scope_key", unique=True), Index("email_login_challenge_token", "token", unique=True), Index("email_login_challenge_expiry", "expires_at"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    surface: Mapped[AuthenticationSurface] = mapped_column(enum_type(AuthenticationSurface), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    code_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    resend_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
