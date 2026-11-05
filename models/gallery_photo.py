from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from models.addressed_mixin import AddressedMixin
from models.gallery import Gallery
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin


class GalleryPhoto(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    """One image of a gallery, where the first position is the one that stands for the whole set."""

    __tablename__ = "gallery_photo"
    __table_args__ = (UniqueConstraint("uuid", name="gallery_photo_uuid"), Index("gallery_photo_listing", "gallery_id", "position"))

    gallery_id: Mapped[int] = mapped_column(BigId, ForeignKey("gallery.id", ondelete="CASCADE"), nullable=False)

    image: Mapped[str] = mapped_column(String(512), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    gallery: Mapped[Gallery] = relationship(Gallery)
