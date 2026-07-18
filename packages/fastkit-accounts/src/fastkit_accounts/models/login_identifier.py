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

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin


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
