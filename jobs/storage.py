import logging

from helpers.db import AsyncSessionLocal
from helpers.scheduler import app
from helpers.settings import settings
from services.sweep import sweep_service

logger = logging.getLogger(__name__)


@app.task("discard_orphan_files", cron="40 4 * * *", queue="storage", timeout=3600)
async def discard_orphan_files():
    """Every file it deletes is one this application wrote down and nothing ever claimed, so it deletes from its own rows and never from a listing of the bucket."""
    if not settings.storage.sweep_orphans:
        return

    async with AsyncSessionLocal() as session:
        logger.info("[cron] discarded %s orphan files", len(await sweep_service.discard_orphans(session)))
