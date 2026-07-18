from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, TimestampMixin, PrimaryKeyMixin
from fastkit_db.types import PortableJSON


class ExecutionStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class ReportExecution(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "report_execution"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    report_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    parameters: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ExecutionStatus.pending.value, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    asset_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    requested_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
