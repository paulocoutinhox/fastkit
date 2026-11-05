from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from helpers.database_base import Base
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.utc_date_time import UtcDateTime


class LoginTicket(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "login_ticket"
    __table_args__ = (Index("login_ticket_token", "token_digest", unique=True), Index("login_ticket_expiry", "expires_at"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    session_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    browser_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
