from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from helpers.dates import now
from models.utc_date_time import UtcDateTime


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=now, onupdate=now, nullable=False)
