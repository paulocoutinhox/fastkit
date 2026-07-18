from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin
from fastkit_permissions.models.scope import PermissionScope


class Permission(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "permission"
    __table_args__ = (UniqueConstraint("code", name="uq_permission_code"),)

    # code is the stable authorization key checked by the authorizer, e.g. "user.view"
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    group: Mapped[str] = mapped_column(
        String(120), default="General", nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str] = mapped_column(
        String(20), default=PermissionScope.tenant.value, nullable=False
    )
