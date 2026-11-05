from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from enums.authentication_surface import AuthenticationSurface
from enums.social_provider import SocialProvider
from helpers.database_base import Base
from models.base import enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.utc_date_time import UtcDateTime


class SocialLoginAttempt(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "social_login_attempt"
    __table_args__ = (Index("social_login_attempt_state", "state_digest", unique=True), Index("social_login_attempt_expiry", "expires_at"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=True)
    session_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    surface: Mapped[AuthenticationSurface] = mapped_column(enum_type(AuthenticationSurface), nullable=False)
    provider: Mapped[SocialProvider] = mapped_column(enum_type(SocialProvider), nullable=False)
    state_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    browser_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    verifier_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    next_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
