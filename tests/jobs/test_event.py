from enums.event import AppEventName, AppEventStatus
from helpers.dates import now
from jobs.event import process_pending_events
from models.event import AppEvent
from tests.factories import save


async def test_the_job_closes_what_the_apps_reported(db, tenant, member):
    event = await save(db, AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="job-uuid", name=AppEventName.PRODUCT_PURCHASED, params={}, occurred_at=now(), status=AppEventStatus.PENDING))

    await process_pending_events()
    await db.refresh(event)

    assert event.status == AppEventStatus.PROCESSED


async def test_the_job_closes_what_died_at_its_last_attempt_before_it_reads_the_queue(db, tenant, member):
    """Closing the stranded rows is a write over the whole table, so it belongs to the job a single node runs and never to the pass."""
    from datetime import timedelta

    from services.delivery import ABANDONED_AFTER
    from services.event import MAX_ATTEMPTS

    event = await save(db, AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="spent", name=AppEventName.PRODUCT_PURCHASED, params={}, occurred_at=now(), status=AppEventStatus.PROCESSING, attempts=MAX_ATTEMPTS, updated_at=now() - ABANDONED_AFTER - timedelta(minutes=1)))

    await process_pending_events()
    await db.refresh(event)

    assert event.status == AppEventStatus.FAILED
