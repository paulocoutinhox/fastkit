from enum import Enum

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin


class PermissionScope(str, Enum):
    global_ = "global"
    tenant = "tenant"
    own = "own"
    custom = "custom"


class Permission(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "permission"
    __table_args__ = (UniqueConstraint("code", name="uq_permission_code"),)

    # code is the stable authorization key checked by the authorizer, e.g. "user.view"
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    group: Mapped[str] = mapped_column(String(120), default="General", nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str] = mapped_column(String(20), default=PermissionScope.tenant.value, nullable=False)


class Role(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "role"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def display_label(self) -> str:
        return self.name


class RolePermission(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "role_permission"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("role.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("permission.id", ondelete="CASCADE"), nullable=False)


class UserRole(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_role"
    __table_args__ = (Index("uq_user_role_tenant", "user_id", "role_id", text("coalesce(tenant_id, 0)"), unique=True),)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("role.id", ondelete="CASCADE"), nullable=False)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
