from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin
from fastkit_db.types import PortableJSON


class AuditLog(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "audit_log"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    effective_tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    before_data: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
