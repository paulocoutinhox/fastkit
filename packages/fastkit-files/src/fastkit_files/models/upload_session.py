from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin
from fastkit_files.models.upload_status import UploadStatus


class UploadSession(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "upload_session"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_alias: Mapped[str] = mapped_column(
        String(40), default="default", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=UploadStatus.pending.value, nullable=False
    )
    max_size_bytes: Mapped[int] = mapped_column(
        Integer, default=10_000_000, nullable=False
    )
    temporary_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("storage_file.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
