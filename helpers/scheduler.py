"""The queue of this application, the worker of this copy, and the trail every run leaves."""

import logging
from datetime import timedelta

from queuefy.app import Queuefy
from queuefy.run import Run
from queuefy.store.sqlalchemy import SqlAlchemyStore
from queuefy.worker import Worker

from enums.system_log import LogCategory, LogLevel
from helpers.db import AsyncSessionLocal, async_engine
from helpers.settings import settings
from services.system_log import system_log_service

logger = logging.getLogger(__name__)

# The runs live in the application database, so every node sees the same schedule and only one of them claims each pass.
store = SqlAlchemyStore(async_engine)
app = Queuefy(store)


def served_queues() -> tuple[str, ...]:
    """An instance serves only the queues it was given, which is how the work is split between nodes instead of doubled."""
    return tuple(settings.cron_queues) if settings.cron_queues else tuple(sorted({task.queue for task in app.tasks.values()}))


def build_worker() -> Worker:
    """The worker of this instance, serving the queues it was told to and reporting every run to the audit trail."""
    worker = Worker(app, queues=served_queues(), concurrency=settings.cron_concurrency, poll=settings.cron_poll_seconds, lease=timedelta(seconds=settings.cron_lease_seconds))

    worker.on_start(started)
    worker.on_finish(finished)
    worker.on_error(failed)

    return worker


async def record(name: str, level: LogLevel, description: str, meta: dict) -> None:
    async with AsyncSessionLocal() as session:
        await system_log_service.record(session, None, None, level, LogCategory.CRON, description, {"job": name, **meta})


async def started(run: Run) -> None:
    await record(run.name, LogLevel.INFO, f'Scheduled service "{run.name}" started', {"attempt": run.attempts})


async def finished(run: Run, result, seconds: float) -> None:
    await record(run.name, LogLevel.SUCCESS, f'Scheduled service "{run.name}" finished', {"duration": round(seconds, 3)})


async def failed(run: Run, error: Exception, seconds: float, retrying: bool) -> None:
    await record(run.name, LogLevel.ERROR, f'Scheduled service "{run.name}" failed', {"duration": round(seconds, 3), "error": str(error), "retrying": retrying})
