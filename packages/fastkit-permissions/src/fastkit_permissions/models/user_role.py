from sqlalchemy import BigInteger, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin


class UserRole(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_role"
    __table_args__ = (
        Index(
            "uq_user_role_tenant",
            "user_id",
            "role_id",
            text("coalesce(tenant_id, 0)"),
            unique=True,
        ),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("role.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
