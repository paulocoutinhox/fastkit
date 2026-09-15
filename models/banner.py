from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.banner import BannerCountKind, BannerPlacement
from helpers.dates import now
from helpers.db import Base
from helpers.search import search_index
from models.base import AddressedMixin, BigId, IdentifiedMixin, TimestampMixin, UtcDateTime, enum_type
from models.language import Language
from models.tenant import Tenant


class Banner(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    """A promoted space on the home whose `url` is opaque here, so adding a destination never needs a schema change."""

    __tablename__ = "banner"
    __table_args__ = (UniqueConstraint("uuid", name="banner_uuid"), Index("banner_window", "placement", "active", "language_id", "starts_at", "ends_at", "position"), search_index("banner_search", "title"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    language_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("language.id", ondelete="RESTRICT"), nullable=True)

    placement: Mapped[BannerPlacement] = mapped_column(enum_type(BannerPlacement), default=BannerPlacement.HOME, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    views: Mapped[int] = mapped_column(BigId, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(BigId, default=0, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
    language: Mapped[Language | None] = relationship(Language)


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
