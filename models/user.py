from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.user import UserAddressType, UserGender, UserRole, UserStatus
from helpers.db import Base
from helpers.search import search_index
from models.base import BigId, IdentifiedMixin, TimestampMixin, UtcDateTime, enum_type, tenant_scoped_unique
from models.language import Language
from models.tenant import Tenant


class User(Base, IdentifiedMixin, TimestampMixin):
    """A single account with four interchangeable login identifiers, named outside by a token that no scope bounds."""

    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("token", name="user_token"),
        tenant_scoped_unique("user_username", "username"),
        tenant_scoped_unique("user_email", "email"),
        tenant_scoped_unique("user_cpf", "cpf"),
        tenant_scoped_unique("user_mobile_phone", "mobile_phone"),
        Index("user_tenant_role", "tenant_id", "role"),
        Index("user_first_name", "first_name"),
        Index("user_last_name", "last_name"),
        search_index("user_search", "first_name", "last_name", "nickname"),
    )

    token: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()), nullable=False)

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    language_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("language.id", ondelete="RESTRICT"), nullable=True)

    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpf: Mapped[str | None] = mapped_column(String(11), nullable=True)
    mobile_phone: Mapped[str | None] = mapped_column(String(16), nullable=True)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    role: Mapped[UserRole] = mapped_column(enum_type(UserRole), default=UserRole.NORMAL, nullable=False)

    # Whether an operator of one brand is also answered the rows that belong to none, which an administrator grants and nobody assumes.
    reaches_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[UserStatus] = mapped_column(enum_type(UserStatus), default=UserStatus.ACTIVE, nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gender: Mapped[UserGender] = mapped_column(enum_type(UserGender), default=UserGender.NONE, nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    recovery_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recovery_token_created_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    failed_sign_ins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sign_in_blocked_until: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    session_epoch: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    erased_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
    language: Mapped[Language | None] = relationship(Language)


class UserAddress(Base, IdentifiedMixin, TimestampMixin):
    """One address per purpose, because a second `main` is two answers to the question the checkout asks once."""

    __tablename__ = "user_address"
    __table_args__ = (UniqueConstraint("user_id", "type", name="user_address_type"), Index("user_address_place", "country_code", "state", "city"))

    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    type: Mapped[UserAddressType] = mapped_column(enum_type(UserAddressType, 16), default=UserAddressType.MAIN, nullable=False)

    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    street_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    complement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(128), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)

    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    user: Mapped[User] = relationship(User)
