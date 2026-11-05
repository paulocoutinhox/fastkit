from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from helpers.dates import now
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.user import User
from models.utc_date_time import UtcDateTime


class ClientRequest(Base, IdentifiedMixin, TimestampMixin):
    """A write a client named, so sending it twice is one piece of work and one answer."""

    __tablename__ = "client_request"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="client_request_key"),)

    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(191), nullable=False)
    answer: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # When the work was taken rather than when the row was born, because taking over a call that died moves this and never the birth of the key.
    claimed_at: Mapped[datetime] = mapped_column(UtcDateTime, default=now, nullable=False)

    user: Mapped[User] = relationship(User)
