import logging

from helpers.db import AsyncSessionLocal
from helpers.scheduler import app
from services.email import email_service

logger = logging.getLogger(__name__)


@app.task("send_pending_emails", cron="*/2 * * * *", queue="email", timeout=110)
async def send_pending_emails():
    """The pass reclaims before it sends, and it is the job that does it because one occurrence of a job is claimed by one node."""
    async with AsyncSessionLocal() as session:
        reclaimed = await email_service.reclaim_abandoned(session)

        if reclaimed:
            logger.info("[cron] handed %s abandoned emails back to the queue", reclaimed)

        logger.info("[cron] sent %s pending emails", len(await email_service.process_pending(session)))
