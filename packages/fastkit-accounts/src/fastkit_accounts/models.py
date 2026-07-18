from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fastkit_db.base import Base, MetadataMixin, TimestampMixin, PrimaryKeyMixin


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


class UserProfile(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "user_profile"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    avatar_file_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")


class LoginIdentifier(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "login_identifier"
    __table_args__ = (
        Index(
            "uq_login_identifier_tenant_type_value",
            text("coalesce(tenant_id, 0)"),
            "type",
            "normalized_value",
            unique=True,
        ),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="identifiers")
