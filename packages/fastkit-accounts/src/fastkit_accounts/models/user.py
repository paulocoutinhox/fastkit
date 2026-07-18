from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin


class User(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "user"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_root: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    preferred_locale: Mapped[str] = mapped_column(
        String(12), default="en", nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    identifiers: Mapped[list["LoginIdentifier"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    profile: Mapped["UserProfile"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    @property
    def full_name(self) -> str:
        parts = [part for part in (self.first_name, self.last_name) if part]

        return " ".join(parts) or (self.display_name or "")

    def display_label(self) -> str:
        return self.display_name or self.full_name or self.email or str(self.id)
