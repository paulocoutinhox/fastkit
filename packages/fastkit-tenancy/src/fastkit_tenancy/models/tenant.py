from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import (
    ActiveFlagMixin,
    Base,
    MetadataMixin,
    PrimaryKeyMixin,
    TimestampMixin,
)
from fastkit_tenancy.models.status import TenantStatus


class Tenant(PrimaryKeyMixin, TimestampMixin, MetadataMixin, ActiveFlagMixin, Base):
    __tablename__ = "tenant"
    __table_args__ = (UniqueConstraint("code", name="uq_tenant_code"),)

    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=TenantStatus.active.value, nullable=False
    )
    default_locale: Mapped[str] = mapped_column(
        String(12), default="en", nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    def display_label(self) -> str:
        return self.name
