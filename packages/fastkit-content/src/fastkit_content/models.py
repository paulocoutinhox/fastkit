from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, TimestampMixin, PrimaryKeyMixin


class ContentType(str, Enum):
    plain_text = "plain_text"
    rich_text = "rich_text"
    html = "html"
    markdown = "markdown"
    json = "json"
    page = "page"
    block = "block"
    email_snippet = "email_snippet"


class ContentStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class Language(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "languages"
    __table_args__ = (UniqueConstraint("code", name="uq_languages_code"),)

    code: Mapped[str] = mapped_column(String(12), nullable=False)
    base_code: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    native_name: Mapped[str] = mapped_column(String(120), nullable=False)
    direction: Mapped[str] = mapped_column(String(3), default="ltr", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def display_label(self) -> str:
        return self.name


class Content(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "contents"
    __table_args__ = (Index("uq_contents_tenant_key", text("coalesce(tenant_id, 0)"), "key", unique=True),)

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default=ContentType.rich_text.value, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ContentStatus.draft.value, nullable=False)
    default_language_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def display_label(self) -> str:
        return self.key


class ContentTranslation(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "content_translations"
    __table_args__ = (UniqueConstraint("content_id", "language_id", name="uq_content_translation"),)

    content_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False, index=True)
    language_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
