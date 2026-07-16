import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fastkit_tasks.cron import CronError, next_run
from fastkit_tasks.models import ScheduledTask, ScheduleType
from fastkit_tasks.queue import TaskQueue

logger = logging.getLogger("fastkit.tasks.scheduler")


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


class Scheduler:
    """Materializes due scheduled tasks into queued executions exactly once per slot."""

    def __init__(self, session_factory, queue: TaskQueue, clock=None):
        self._session_factory = session_factory
        self._queue = queue
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def tick(self) -> int:
        now = self._clock()
        materialized = 0

        async with self._session_factory() as session:
            due = (
                await session.execute(
                    select(ScheduledTask).where(ScheduledTask.enabled.is_(True), ScheduledTask.next_run_at.isnot(None), ScheduledTask.next_run_at <= now)
                )
            ).scalars().all()

        for task in due:
            if await self._materialize(task, now):
                materialized += 1

        return materialized

    async def _materialize(self, task: ScheduledTask, now: datetime) -> bool:
        slot = _aware(task.next_run_at)

        try:
            await self._queue.enqueue(
                task_name=task.task_name,
                payload=task.payload,
                queue=task.queue,
                available_at=slot,
                tenant_id=task.tenant_id,
                scheduled_task_id=task.id,
                scheduled_for=slot,
            )
        except IntegrityError:
            await self._advance(task, now)

            return False
        except Exception:
            logger.exception("failed to materialize scheduled task %s", task.id)

            return False

        await self._advance(task, now)

        return True

    async def _advance(self, task: ScheduledTask, now: datetime) -> None:
        upcoming = self._compute_next(task, now)

        async with self._session_factory() as session:
            stored = await session.get(ScheduledTask, task.id)
            stored.last_run_at = now
            stored.next_run_at = upcoming
            stored.enabled = upcoming is not None and stored.enabled
            stored.version += 1
            await session.commit()

    def _compute_next(self, task: ScheduledTask, now: datetime) -> datetime | None:
        if task.schedule_type == ScheduleType.cron.value:
            try:
                return next_run(task.cron_expression, now)
            except CronError:
                logger.exception("disabling scheduled task %s with invalid cron '%s'", task.id, task.cron_expression)

                return None

        if task.schedule_type == ScheduleType.interval.value:
            return now + timedelta(seconds=task.interval_seconds)

        return None
