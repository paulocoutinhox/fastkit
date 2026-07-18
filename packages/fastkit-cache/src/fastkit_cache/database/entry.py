from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin


class CacheEntry(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cache_entry"
    __table_args__ = (
        UniqueConstraint("namespace", "key_hash", name="uq_cache_namespace_key"),
    )

    namespace: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(500), nullable=False)
    value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
