from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin
from fastkit_content.models.content_status import ContentStatus
from fastkit_content.models.content_type import ContentType


class Content(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "content"
    __table_args__ = (
        Index(
            "uq_content_tenant_key", text("coalesce(tenant_id, 0)"), "key", unique=True
        ),
    )

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(
        String(20), default=ContentType.rich_text.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=ContentStatus.draft.value, nullable=False
    )
    default_language_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def display_label(self) -> str:
        return self.key
