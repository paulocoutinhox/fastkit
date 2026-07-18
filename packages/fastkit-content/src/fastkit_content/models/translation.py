from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin


class ContentTranslation(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "content_translation"
    __table_args__ = (
        UniqueConstraint("content_id", "language_id", name="uq_content_translation"),
    )

    content_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
