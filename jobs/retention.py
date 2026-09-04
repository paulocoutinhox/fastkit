import logging

from helpers.db import AsyncSessionLocal
from helpers.scheduler import app
from services.retention import retention_service

logger = logging.getLogger(__name__)


@app.task("discard_expired_records", cron="20 4 * * *", queue="retention", timeout=3600)
async def discard_expired_records():
    async with AsyncSessionLocal() as session:
        logger.info("[cron] retention: %s", await retention_service.discard(session))
