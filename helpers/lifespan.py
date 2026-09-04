"""What the process does when it starts and what it stops before it ends."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Importing a job is what declares it on the queue, and this is what runs a worker over them, so the two travel together.
import jobs.email  # noqa: F401
import jobs.event  # noqa: F401
import jobs.retention  # noqa: F401
import jobs.storage  # noqa: F401
import jobs.subscription  # noqa: F401
from helpers.scheduler import build_worker
from helpers.schema import create_schema
from helpers.settings import settings

# What the published configuration writes where a secret goes, so an installation that never filled it in is one that says so.
PLACEHOLDER = "change-me"

logger = logging.getLogger(__name__)


def refuse_a_secret_this_repository_publishes() -> None:
    """Every signed cookie and every stored credential rests on these, and the value the template ships is one anybody can read here."""
    carried = {"security.secret_key": settings.security.secret_key} | {f"security.encryption_keys[{index}]": key for index, key in enumerate(settings.security.encryption_keys)}
    named = sorted(name for name, value in carried.items() if PLACEHOLDER in value)

    if named:
        raise RuntimeError(f"{', '.join(named)} still carries the placeholder this repository publishes, and no environment serves with a secret anybody can read")


@asynccontextmanager
async def lifespan(app: FastAPI):
    refuse_a_secret_this_repository_publishes()

    await create_schema()

    if not settings.cron_enabled:
        yield

        return

    worker = build_worker()
    logger.info("[cron] %s serving %s", worker.name, ", ".join(worker.queues))
    polling = asyncio.create_task(worker.run())

    try:
        yield
    finally:
        # What is already running is given the chance to finish, so a deploy never cuts a pass in half.
        worker.stop()
        await polling
