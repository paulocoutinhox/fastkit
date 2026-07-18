from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update

from fastkit_tasks.models import ExecutionStatus, TaskExecution
from fastkit_tasks.retry import RetryPolicy, compute_delay


class TaskQueue:
    """Persistent task queue with a portable, contention-safe leasing protocol."""

    def __init__(self, database, registry=None, clock=None):
        self._database = database
        self._registry = registry
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def enqueue(self, task_name: str, payload: dict | None = None, queue: str = "default", available_at: datetime | None = None, max_attempts: int | None = None, timeout: int | None = None, retry_delay: int | None = None, idempotency_key: str | None = None, tenant_id: int | None = None, scheduled_task_id=None, scheduled_for: datetime | None = None) -> TaskExecution:
        # the task's declared policy is the default, and an explicit argument still overrides it
        definition = self._registry.get(task_name) if self._registry is not None and self._registry.contains(task_name) else None
        attempts = max_attempts if max_attempts is not None else definition.max_attempts if definition is not None else 1
        timeout_seconds = timeout if timeout is not None else definition.timeout if definition is not None else 60
        delay = retry_delay if retry_delay is not None else definition.retry_delay if definition is not None else 5

        async with self._database.session_factory() as session:
            if idempotency_key is not None:
                existing = (await session.execute(select(TaskExecution).where(TaskExecution.idempotency_key == idempotency_key))).scalar_one_or_none()

                if existing is not None:
                    return existing

            execution = TaskExecution(
                task_name=task_name,
                payload=payload,
                queue=queue,
                available_at=available_at or self._clock(),
                max_attempts=attempts,
                timeout_seconds=timeout_seconds,
                retry_delay_seconds=delay,
                idempotency_key=idempotency_key,
                tenant_id=tenant_id,
                scheduled_task_id=scheduled_task_id,
                scheduled_for=scheduled_for,
            )
            session.add(execution)
            await session.commit()
            await session.refresh(execution)

            return execution

    async def lease(self, worker_id: str, queues: list[str], lease_seconds: int = 60) -> TaskExecution | None:
        now = self._clock()

        async with self._database.session_factory() as session:
            candidates = (
                await session.execute(
                    select(TaskExecution.id)
                    .where(
                        TaskExecution.queue.in_(queues),
                        TaskExecution.status.in_([ExecutionStatus.pending.value, ExecutionStatus.retrying.value]),
                        TaskExecution.available_at <= now,
                    )
                    .order_by(TaskExecution.priority.desc(), TaskExecution.available_at.asc())
                    .limit(10)
                )
            ).scalars().all()

            for execution_id in candidates:
                locked = await self._try_lock(session, execution_id, worker_id, now, lease_seconds)

                if locked is not None:
                    return locked

            return None

    async def _try_lock(self, session, execution_id, worker_id, now, lease_seconds) -> TaskExecution | None:
        result = await session.execute(
            update(TaskExecution)
            .where(
                TaskExecution.id == execution_id,
                TaskExecution.status.in_([ExecutionStatus.pending.value, ExecutionStatus.retrying.value]),
                TaskExecution.available_at <= now,
                or_(TaskExecution.locked_until.is_(None), TaskExecution.locked_until < now),
            )
            .values(
                status=ExecutionStatus.running.value,
                locked_by=worker_id,
                locked_until=now + timedelta(seconds=lease_seconds),
                started_at=now,
                heartbeat_at=now,
                attempt_count=TaskExecution.attempt_count + 1,
            )
        )

        if result.rowcount != 1:
            await session.rollback()

            return None

        await session.commit()

        return await session.get(TaskExecution, execution_id)

    async def heartbeat(self, execution_id, worker_id: str, lease_seconds: int = 60, progress: int | None = None, message: str | None = None) -> bool:
        now = self._clock()

        async with self._database.session_factory() as session:
            values = {"heartbeat_at": now, "locked_until": now + timedelta(seconds=lease_seconds)}

            if progress is not None:
                values["progress"] = progress

            if message is not None:
                values["progress_message"] = message

            result = await session.execute(
                update(TaskExecution).where(TaskExecution.id == execution_id, TaskExecution.locked_by == worker_id).values(**values)
            )
            await session.commit()

            return result.rowcount == 1

    async def complete(self, execution_id, worker_id: str, result: dict | None = None) -> bool:
        return await self._finalize(execution_id, worker_id, ExecutionStatus.succeeded.value, result=result)

    async def fail(self, execution_id, worker_id: str, error_code: str, error_message: str, retryable: bool = True, retry_policy: RetryPolicy = RetryPolicy.exponential, jitter_source: float = 0.0) -> str | None:
        now = self._clock()

        async with self._database.session_factory() as session:
            execution = await session.get(TaskExecution, execution_id)
            can_retry = retryable and execution.attempt_count < execution.max_attempts

            if can_retry:
                delay = compute_delay(retry_policy, execution.retry_delay_seconds, execution.attempt_count, jitter_source)
                values = {"status": ExecutionStatus.retrying.value, "available_at": now + timedelta(seconds=delay), "locked_by": None, "locked_until": None, "error_code": error_code, "error_message": error_message}
            else:
                values = {"status": ExecutionStatus.failed.value, "finished_at": now, "locked_by": None, "locked_until": None, "error_code": error_code, "error_message": error_message}

            result = await session.execute(
                update(TaskExecution).where(TaskExecution.id == execution_id, TaskExecution.locked_by == worker_id, TaskExecution.status == ExecutionStatus.running.value).values(**values)
            )
            await session.commit()

            return values["status"] if result.rowcount == 1 else None

    async def cancel(self, execution_id) -> bool:
        now = self._clock()

        async with self._database.session_factory() as session:
            result = await session.execute(
                update(TaskExecution)
                .where(TaskExecution.id == execution_id, TaskExecution.status.in_([ExecutionStatus.pending.value, ExecutionStatus.retrying.value]))
                .values(status=ExecutionStatus.cancelled.value, finished_at=now)
            )
            await session.commit()

            return result.rowcount == 1

    async def _finalize(self, execution_id, worker_id, status, result=None) -> bool:
        now = self._clock()

        async with self._database.session_factory() as session:
            outcome = await session.execute(
                update(TaskExecution)
                .where(TaskExecution.id == execution_id, TaskExecution.locked_by == worker_id, TaskExecution.status == ExecutionStatus.running.value)
                .values(status=status, finished_at=now, progress=100, result=result, locked_by=None, locked_until=None)
            )
            await session.commit()

            return outcome.rowcount == 1

    async def reclaim_expired(self, grace_seconds: int = 0) -> int:
        now = self._clock()
        cutoff = now - timedelta(seconds=grace_seconds)
        expired = (TaskExecution.status == ExecutionStatus.running.value, TaskExecution.locked_until < cutoff)

        async with self._database.session_factory() as session:
            failed = await session.execute(
                update(TaskExecution)
                .where(*expired, TaskExecution.attempt_count >= TaskExecution.max_attempts)
                .values(status=ExecutionStatus.failed.value, locked_by=None, locked_until=None, finished_at=now)
            )
            retrying = await session.execute(
                update(TaskExecution)
                .where(*expired, TaskExecution.attempt_count < TaskExecution.max_attempts)
                .values(status=ExecutionStatus.retrying.value, locked_by=None, locked_until=None, available_at=now)
            )
            await session.commit()

            return failed.rowcount + retrying.rowcount
