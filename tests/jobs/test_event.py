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
