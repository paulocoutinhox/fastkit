"""An instance that runs for years is one that still answers, and what makes it stop is a table nobody ever trimmed."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from enums.banner import BannerCountKind
from enums.email import OutboundEmailStatus
from enums.event import AppEventStatus
from enums.integration import WebhookEventStatus
from enums.system_log import LogCategory, LogLevel
from helpers.dates import now
from helpers.settings import settings
from models.banner import BannerImpression
from models.email import OutboundEmail
from models.event import AppEvent
from models.idempotency import ClientRequest
from models.integration import WebhookEvent
from models.system_log import SystemLog
from services.email import MAX_ATTEMPTS as EMAIL_ATTEMPTS
from services.event import MAX_ATTEMPTS as EVENT_ATTEMPTS
from services.retention import retention_service
from services.system_log import system_log_service
from services.webhook import MAX_ATTEMPTS as WEBHOOK_ATTEMPTS
from tests.factories import make_banner, make_integration, save


async def aged(db, model, record, days: int):
    """The column is written by the mixin, so a row of the past is one whose stamp is moved after it exists."""
    await db.execute(update(model).where(model.id == record.id).values(created_at=now() - timedelta(days=days)))
    await db.commit()

    return record


async def count_of(db, model) -> int:
    return await db.scalar(select(func.count()).select_from(model))


async def test_a_log_older_than_the_window_stops_being_kept(db, tenant):
    old = await system_log_service.record(db, tenant.id, None, LogLevel.INFO, LogCategory.CRON, "an old pass", {})
    await system_log_service.record(db, tenant.id, None, LogLevel.INFO, LogCategory.CRON, "a pass of today", {})
    await db.commit()

    await aged(db, SystemLog, old, settings.retention.system_log_days + 1)

    assert (await retention_service.discard(db))["system_log"] == 1
    assert await count_of(db, SystemLog) == 1


async def test_a_window_of_zero_keeps_everything(db, tenant, monkeypatch):
    """An installation that has to keep every line says so, and nothing argues with it."""
    monkeypatch.setattr(settings.retention, "system_log_days", 0)

    old = await system_log_service.record(db, tenant.id, None, LogLevel.INFO, LogCategory.CRON, "an old pass", {})
    await db.commit()
    await aged(db, SystemLog, old, 4000)

    assert "system_log" not in await retention_service.discard(db)
    assert await count_of(db, SystemLog) == 1


@pytest.mark.parametrize("status,kept", [(AppEventStatus.PROCESSED, False), (AppEventStatus.IGNORED, False), (AppEventStatus.PENDING, True), (AppEventStatus.FAILED, True)])
async def test_only_an_event_nothing_will_read_again_is_dropped(db, tenant, member, status, kept):
    """What the retry still picks up stays, however old it is, or the pass would delete the work it was about to do."""
    record = await save(db, AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="event-1", name="app_opened", status=status, occurred_at=now(), params={}))
    await aged(db, AppEvent, record, settings.retention.app_event_days + 1)

    await retention_service.discard(db)

    assert (await count_of(db, AppEvent) == 1) is kept


async def test_an_event_that_spent_every_attempt_is_dropped_even_though_it_failed(db, tenant, member):
    record = await save(db, AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="event-2", name="app_opened", status=AppEventStatus.FAILED, attempts=EVENT_ATTEMPTS, occurred_at=now(), params={}))
    await aged(db, AppEvent, record, settings.retention.app_event_days + 1)

    await retention_service.discard(db)

    assert await count_of(db, AppEvent) == 0


async def test_a_notice_the_gateway_may_still_resend_outlives_the_window(db, tenant):
    """The row is the memory that the notice already arrived, and a gateway retries for hours and not for months."""
    integration = await make_integration(db, tenant)
    record = await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id="evt-1", status=WebhookEventStatus.FAILED, attempts=1, payload={}, payload_hash="a"))
    await aged(db, WebhookEvent, record, settings.retention.webhook_event_days + 1)

    await retention_service.discard(db)

    assert await count_of(db, WebhookEvent) == 1


async def test_a_notice_that_was_settled_stops_being_kept(db, tenant):
    integration = await make_integration(db, tenant)
    record = await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id="evt-2", status=WebhookEventStatus.COMPLETED, payload={}, payload_hash="b"))
    await aged(db, WebhookEvent, record, settings.retention.webhook_event_days + 1)

    await retention_service.discard(db)

    assert await count_of(db, WebhookEvent) == 0


async def test_a_message_that_went_out_stops_being_kept_and_one_still_queued_does_not(db, tenant):
    sent = await save(db, OutboundEmail(tenant_id=tenant.id, to_address="reader@acme.com", subject="Sent", template="welcome", locale="en", status=OutboundEmailStatus.SENT, sent_at=now()))
    queued = await save(db, OutboundEmail(tenant_id=tenant.id, to_address="reader@acme.com", subject="Queued", template="welcome", locale="en"))
    spent = await save(db, OutboundEmail(tenant_id=tenant.id, to_address="reader@acme.com", subject="Spent", template="welcome", locale="en", status=OutboundEmailStatus.FAILED, attempts=EMAIL_ATTEMPTS))

    for record in (sent, queued, spent):
        await aged(db, OutboundEmail, record, settings.retention.outbound_email_days + 1)

    assert (await retention_service.discard(db))["outbound_email"] == 2
    assert (await db.scalar(select(OutboundEmail.subject))) == "Queued"


async def test_the_pass_walks_a_table_out_in_bites(db, tenant, monkeypatch):
    """The first pass over a table nobody trimmed deletes millions, and one statement would hold it for minutes."""
    monkeypatch.setattr(settings.retention, "batch", 2)

    for index in range(5):
        record = await system_log_service.record(db, tenant.id, None, LogLevel.INFO, LogCategory.CRON, f"pass {index}", {})
        await db.commit()
        await aged(db, SystemLog, record, settings.retention.system_log_days + 1)

    assert (await retention_service.discard(db))["system_log"] == 5
    assert await count_of(db, SystemLog) == 0


async def test_the_queue_stops_keeping_a_run_nothing_reads_again(db):
    """Queuefy writes one row per occurrence of every job, and a year of them is a table nobody ever asked for."""
    assert (await retention_service.discard(db))["cron_run"] == 0


async def test_a_queue_window_of_zero_keeps_every_run(db, monkeypatch):
    monkeypatch.setattr(settings.retention, "cron_run_days", 0)

    assert (await retention_service.discard(db))["cron_run"] == 0


async def test_a_notice_that_spent_every_attempt_is_dropped(db, tenant):
    integration = await make_integration(db, tenant)
    record = await save(db, WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, external_event_id="evt-3", status=WebhookEventStatus.FAILED, attempts=WEBHOOK_ATTEMPTS, payload={}, payload_hash="c"))
    await aged(db, WebhookEvent, record, settings.retention.webhook_event_days + 1)

    await retention_service.discard(db)

    assert await count_of(db, WebhookEvent) == 0


async def test_a_name_a_client_gave_stops_being_kept_once_nobody_is_repeating_that_call(db, member):
    """The keys of every named write are one more table that grows for good, and past the window no client is still sending that call."""
    answered = await save(db, ClientRequest(user_id=member.id, idempotency_key="answered", endpoint="commerce-product-checkout", answer={"url": "https://gateway.acme.com/one"}))
    await save(db, ClientRequest(user_id=member.id, idempotency_key="working", endpoint="commerce-product-checkout"))

    await aged(db, ClientRequest, answered, settings.retention.client_request_days + 1)

    assert (await retention_service.discard(db))["client_request"] == 1
    assert await count_of(db, ClientRequest) == 1


async def test_a_name_still_being_worked_on_is_never_trimmed_however_old_it_is(db, member):
    """A key with no answer on it is a call somebody may still be inside, and dropping it opens the payment a second time."""
    working = await save(db, ClientRequest(user_id=member.id, idempotency_key="stuck", endpoint="commerce-product-checkout"))

    await aged(db, ClientRequest, working, 4000)

    assert (await retention_service.discard(db))["client_request"] == 0
    assert await count_of(db, ClientRequest) == 1


async def test_an_old_banner_impression_leaves_its_aggregate_behind(db, tenant):
    banner = await make_banner(db, tenant, views=1)
    impression = await save(db, BannerImpression(banner_id=banner.id, kind=BannerCountKind.VIEW, visitor="reader", day=now().date()))
    await aged(db, BannerImpression, impression, settings.retention.banner_impression_days + 1)

    assert (await retention_service.discard(db))["banner_impression"] == 1
    await db.refresh(banner)
    assert banner.views == 1
