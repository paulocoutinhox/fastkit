from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin
from fastkit_files.models.file_status import StorageFileStatus
from fastkit_files.models.kind import StorageFileKind


class StorageFile(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "storage_file"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(
        String(20), default=StorageFileKind.file.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=StorageFileStatus.pending_upload.value,
        nullable=False,
        index=True,
    )

    storage_alias: Mapped[str] = mapped_column(
        String(40), default="default", nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    visibility: Mapped[str] = mapped_column(
        String(20), default="private", nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
