from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.banner_placement import BannerPlacement
from helpers.database_base import Base
from helpers.search import search_index
from models.addressed_mixin import AddressedMixin
from models.base import enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.language import Language
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin
from models.utc_date_time import UtcDateTime


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
