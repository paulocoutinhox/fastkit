from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, TimestampMixin, PrimaryKeyMixin
from fastkit_db.types import PortableJSON


class SystemLog(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "system_log"

    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    request_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    module: Mapped[str | None] = mapped_column(String(120), nullable=True)
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    exception_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exception_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)

    payload: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)


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
