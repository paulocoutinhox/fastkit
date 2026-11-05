from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from helpers.database_base import Base
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin


class StoredFileMention(Base, IdentifiedMixin, TimestampMixin):
    """A row that names a stored file, one per row and per file: a file leaves the bucket only once nothing names it, whoever else it was pasted into."""

    __tablename__ = "stored_file_mention"
    __table_args__ = (UniqueConstraint("stored_file_id", "owner", name="stored_file_mention_owner"), Index("stored_file_mention_by_owner", "owner"))

    stored_file_id: Mapped[int] = mapped_column(BigId, ForeignKey("stored_file.id", ondelete="CASCADE"), nullable=False)

    # The table and the id of the row that names it, because a file is named from many tables and a key into each would be a column per table.
    owner: Mapped[str] = mapped_column(String(96), nullable=False)
