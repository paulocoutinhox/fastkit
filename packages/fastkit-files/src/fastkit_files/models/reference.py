from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin


class StorageFileReference(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "storage_file_reference"

    storage_file_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("storage_file.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_type: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    slot: Mapped[str] = mapped_column(String(80), default="default", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
