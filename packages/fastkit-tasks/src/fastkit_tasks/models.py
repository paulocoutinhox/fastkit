from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, TimestampMixin, PrimaryKeyMixin
from fastkit_db.types import PortableJSON


class ScheduleType(str, Enum):
    once = "once"
    interval = "interval"
    cron = "cron"


class ExecutionStatus(str, Enum):
    pending = "pending"
    running = "running"
    retrying = "retrying"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class ScheduledTask(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "scheduled_task"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    task_name: Mapped[str] = mapped_column(String(200), nullable=False)

    schedule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(120), nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    payload: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    queue: Mapped[str] = mapped_column(String(80), default="default", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class TaskExecution(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "task_execution"
    __table_args__ = (UniqueConstraint("scheduled_task_id", "scheduled_for", name="uq_execution_schedule_slot"),)

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    scheduled_task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    task_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    queue: Mapped[str] = mapped_column(String(80), default="default", nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default=ExecutionStatus.pending.value, nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_message: Mapped[str | None] = mapped_column(String(255), nullable=True)

    result: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class TaskAttempt(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_attempt"

    task_execution_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
