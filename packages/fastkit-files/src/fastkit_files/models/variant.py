from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin


class StorageFileVariant(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "storage_file_variant"
    __table_args__ = (
        UniqueConstraint(
            "storage_file_id", "name", name="uq_storage_file_variant_name"
        ),
    )

    storage_file_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("storage_file.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ready", nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
