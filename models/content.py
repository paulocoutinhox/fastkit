from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.db import Base
from helpers.search import search_index
from models.base import AddressedMixin, BigId, IdentifiedMixin, TimestampMixin, language_scoped_unique, tenant_scoped_unique
from models.language import Language
from models.tenant import Tenant


class ContentCategory(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    __tablename__ = "content_category"
    __table_args__ = (UniqueConstraint("uuid", name="content_category_uuid"), tenant_scoped_unique("content_category_tag", "tag"), Index("content_category_name", "name"), search_index("content_category_search", "name"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tag: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)


class Content(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    __tablename__ = "content"
    __table_args__ = (UniqueConstraint("uuid", name="content_uuid"), language_scoped_unique("content_tenant_tag", "tag"), Index("content_title", "title"), Index("content_published_at", "published_at"), search_index("content_search", "title"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    category_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("content_category.id", ondelete="RESTRICT"), nullable=True)
    language_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("language.id", ondelete="RESTRICT"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    tag: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
    category: Mapped[ContentCategory | None] = relationship(ContentCategory)
    language: Mapped[Language | None] = relationship(Language)
