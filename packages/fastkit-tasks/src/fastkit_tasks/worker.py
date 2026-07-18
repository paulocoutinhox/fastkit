import asyncio
import logging
from datetime import datetime, timezone

from fastkit_tasks.models import TaskAttempt
from fastkit_tasks.registry import PermanentTaskError, TaskRegistry
from fastkit_tasks.queue import TaskQueue
from fastkit_tasks.retry import RetryPolicy

logger = logging.getLogger("fastkit.tasks")


class TaskContext:
    """Handed to a task handler so it can report progress and extend its lease."""

    def __init__(self, queue: TaskQueue, execution, worker_id: str, lease_seconds: int):
        self.queue = queue
        self.execution = execution
        self.worker_id = worker_id
        self._lease_seconds = lease_seconds

    async def heartbeat(self, progress: int | None = None, message: str | None = None) -> None:
        await self.queue.heartbeat(self.execution.id, self.worker_id, self._lease_seconds, progress, message)


class Worker:
    """Leases one execution at a time, runs it under a timeout and records the attempt."""

    def __init__(self, queue: TaskQueue, registry: TaskRegistry, database, worker_id: str, queues: list[str] | None = None, lease_seconds: int = 60, clock=None):
        self._queue = queue
        self._registry = registry
        self._database = database
        self._worker_id = worker_id
        self._queues = queues or ["default"]
        self._lease_seconds = lease_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def run_once(self) -> str | None:
        execution = await self._queue.lease(self._worker_id, self._queues, self._lease_seconds)

        if execution is None:
            return None

        started = self._clock()

        try:
            definition = self._registry.get(execution.task_name)
        except KeyError:
            message = f"task '{execution.task_name}' is not registered"
            status = await self._queue.fail(execution.id, self._worker_id, "task.unregistered", message, retryable=False)
            await self._record_attempt(execution, "failed", started, "task.unregistered", message)

            return status

        context = TaskContext(self._queue, execution, self._worker_id, self._lease_seconds)

        try:
            result = await asyncio.wait_for(definition.handler(context, execution.payload or {}), timeout=execution.timeout_seconds)
        except PermanentTaskError as error:
            status = await self._queue.fail(execution.id, self._worker_id, "task.permanent", str(error), retryable=False)
            await self._record_attempt(execution, "failed", started, "task.permanent", str(error))

            return status
        except asyncio.TimeoutError:
            status = await self._queue.fail(execution.id, self._worker_id, "task.timeout", "task timed out", retryable=True, retry_policy=RetryPolicy.exponential)
            await self._record_attempt(execution, "failed", started, "task.timeout", "task timed out")

            return status
        except Exception as error:
            status = await self._queue.fail(execution.id, self._worker_id, "task.error", str(error), retryable=True)
            await self._record_attempt(execution, "failed", started, "task.error", str(error))

            return status

        await self._queue.complete(execution.id, self._worker_id, result if isinstance(result, dict) else None)
        await self._record_attempt(execution, "succeeded", started, None, None)

        return "succeeded"

    async def drain(self, scheduler=None) -> None:
        """Materialize due scheduled work, reclaim lost leases, then run every ready execution."""

        if scheduler is not None:
            await scheduler.tick()

        await self._queue.reclaim_expired()

        while await self.run_once() is not None:
            pass

    async def run(self, poll_interval: float = 1.0, scheduler=None) -> None:
        """Long-running loop: drain the queue, sleep, repeat until cancelled.

        `asyncio.CancelledError` is a `BaseException`, so it is never swallowed by the
        `except Exception` guard; the loop always sleeps afterwards to yield the event loop.
        """

        while True:
            try:
                await self.drain(scheduler)
            except Exception:
                logger.exception("task worker cycle failed")

            await asyncio.sleep(poll_interval)

    async def _record_attempt(self, execution, status, started, error_code, error_message) -> None:
        async with self._database.session_factory() as session:
            session.add(
                TaskAttempt(
                    task_execution_id=execution.id,
                    attempt_number=execution.attempt_count,
                    worker_id=self._worker_id,
                    status=status,
                    started_at=started,
                    finished_at=self._clock(),
                    error_code=error_code,
                    error_message=error_message,
                )
            )
            await session.commit()
