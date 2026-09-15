import logging

from helpers.db import AsyncSessionLocal
from helpers.scheduler import app
from services.event import app_event_service

logger = logging.getLogger(__name__)


@app.task("process_pending_events", cron="*/10 * * * *", queue="event", timeout=590)
async def process_pending_events():
    async with AsyncSessionLocal() as session:
        logger.info("[cron] processed %s reported events", len(await app_event_service.process_pending(session)))
