from datetime import datetime

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from enums.upload import UploadPurpose
from helpers.db import Base
from models.base import BigId, IdentifiedMixin, TimestampMixin, UtcDateTime, enum_type


class StoredFile(Base, IdentifiedMixin, TimestampMixin):
    """Every file this application wrote, which is where a uuid answers the key it was written under and where an orphan pass reads instead of the bucket."""

    __tablename__ = "stored_file"
    __table_args__ = (UniqueConstraint("uuid", name="stored_file_uuid"), Index("stored_file_waiting", "claimed_at", "created_at"))

    uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    key: Mapped[str] = mapped_column(String(512), nullable=False)
    purpose: Mapped[UploadPurpose] = mapped_column(enum_type(UploadPurpose, 32), nullable=False)
    size: Mapped[int] = mapped_column(BigId, nullable=False)

    # The pass looks for what nothing has claimed, which is the rare value here and the reason this pair is indexed.
    claimed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
