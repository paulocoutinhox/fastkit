from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, TimestampMixin, PrimaryKeyMixin


class StorageFileKind(str, Enum):
    file = "file"
    image = "image"
    video = "video"
    audio = "audio"
    document = "document"
    other = "other"


class StorageFileStatus(str, Enum):
    pending_upload = "pending_upload"
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class UploadStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    expired = "expired"


class StorageFile(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "storage_file"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), default=StorageFileKind.file.value, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=StorageFileStatus.pending_upload.value, nullable=False, index=True)

    storage_alias: Mapped[str] = mapped_column(String(40), default="default", nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    visibility: Mapped[str] = mapped_column(String(20), default="private", nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class StorageFileVariant(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "storage_file_variant"
    __table_args__ = (UniqueConstraint("storage_file_id", "name", name="uq_storage_file_variant_name"),)

    storage_file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("storage_file.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ready", nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class StorageFileReference(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "storage_file_reference"

    storage_file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("storage_file.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    slot: Mapped[str] = mapped_column(String(80), default="default", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UploadSession(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "upload_session"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_alias: Mapped[str] = mapped_column(String(40), default="default", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=UploadStatus.pending.value, nullable=False)
    max_size_bytes: Mapped[int] = mapped_column(Integer, default=10_000_000, nullable=False)
    temporary_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_file_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("storage_file.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
