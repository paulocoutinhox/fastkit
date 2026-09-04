from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.db import Base
from helpers.search import search_index
from models.base import AddressedMixin, BigId, IdentifiedMixin, TimestampMixin, language_scoped_unique
from models.language import Language
from models.tenant import Tenant


class Gallery(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    """A set of images published under a tag, where the language is what picks between two galleries sharing one."""

    __tablename__ = "gallery"
    __table_args__ = (UniqueConstraint("uuid", name="gallery_uuid"), language_scoped_unique("gallery_tenant_tag", "tag"), Index("gallery_published_at", "published_at"), Index("gallery_listing", "tenant_id", "active", "position"), search_index("gallery_search", "title"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    language_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("language.id", ondelete="RESTRICT"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    tag: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
    language: Mapped[Language | None] = relationship(Language)


class GalleryPhoto(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    """One image of a gallery, where the first position is the one that stands for the whole set."""

    __tablename__ = "gallery_photo"
    __table_args__ = (UniqueConstraint("uuid", name="gallery_photo_uuid"), Index("gallery_photo_listing", "gallery_id", "position"))

    gallery_id: Mapped[int] = mapped_column(BigId, ForeignKey("gallery.id", ondelete="CASCADE"), nullable=False)

    image: Mapped[str] = mapped_column(String(512), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    gallery: Mapped[Gallery] = relationship(Gallery)
