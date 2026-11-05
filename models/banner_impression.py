from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.banner_count_kind import BannerCountKind
from helpers.database_base import Base
from helpers.dates import now
from models.banner import Banner
from models.base import enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.utc_date_time import UtcDateTime


class BannerImpression(Base, IdentifiedMixin, TimestampMixin):
    """One view or one click of one banner by one visitor on one day, which is the key that makes counting it twice impossible."""

    __tablename__ = "banner_impression"
    __table_args__ = (UniqueConstraint("banner_id", "kind", "visitor", "day", name="banner_impression_once"), Index("banner_impression_window", "banner_id", "occurred_at"))

    banner_id: Mapped[int] = mapped_column(BigId, ForeignKey("banner.id", ondelete="CASCADE"), nullable=False)

    kind: Mapped[BannerCountKind] = mapped_column(enum_type(BannerCountKind), nullable=False)
    visitor: Mapped[str] = mapped_column(String(64), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, default=now, nullable=False)

    banner: Mapped[Banner] = relationship(Banner)
