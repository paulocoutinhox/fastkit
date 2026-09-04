import logging

from helpers.db import AsyncSessionLocal
from helpers.scheduler import app
from services.delivery import delivery_service
from services.reconciliation import reconciliation_service
from services.webhook import webhook_service

logger = logging.getLogger(__name__)


async def run_subscription_cycle(session) -> dict:
    """One pass in one order: the provider speaks before the clock closes anything, and what is still open is delivered."""
    reconciled = await reconciliation_service.reconcile_stale(session)
    expired = await delivery_service.expire_subscriptions(session)
    delivered = await delivery_service.process_due(session)
    grants = await delivery_service.retry_failed_grants(session)
    events = await webhook_service.retry_failed(session)

    return {"reconciled": reconciled, "expired": len(expired), "delivered": len(delivered), "retried_grants": len(grants), "retried_events": len(events)}


@app.task("run_subscription_cycle", cron="*/5 * * * *", queue="subscription", timeout=290)
async def subscription_cycle():
    async with AsyncSessionLocal() as session:
        logger.info("[cron] subscription cycle: %s", await run_subscription_cycle(session))
