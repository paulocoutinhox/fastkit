from uuid import uuid4

import pytest
from sqlalchemy import select

import services.app_event_service as services_app_event_service_module
from enums.app_event_name import AppEventName
from enums.app_event_status import AppEventStatus
from enums.log_category import LogCategory
from helpers.dates import now
from models.app_event import AppEvent
from models.system_log import SystemLog
from services.app_event_service import MAX_ATTEMPTS, app_event_service
from tests.factories import save


async def report(db, tenant, member, name: str, params: dict | None = None) -> AppEvent:
    return await save(db, AppEvent(tenant_id=tenant.id, user_id=member.id, uuid=str(uuid4()), name=name, params=params or {}, occurred_at=now(), status=AppEventStatus.PENDING))


async def logs(db) -> list[SystemLog]:
    return list((await db.execute(select(SystemLog))).scalars())


@pytest.mark.parametrize("name,category", [("product-purchased", LogCategory.PURCHASE), ("checkout-started", LogCategory.PURCHASE), ("content-viewed", LogCategory.CONTENT), ("gallery-viewed", LogCategory.CONTENT)])
async def test_a_reported_event_becomes_a_line_of_the_system_log_in_its_own_category(db, tenant, member, name, category):
    await report(db, tenant, member, name, {"product_id": 7})

    processed = await app_event_service.process_pending(db)
    entries = await logs(db)

    assert processed[0].status == AppEventStatus.PROCESSED
    assert entries[0].category == category
    assert entries[0].meta == {"product_id": 7}
    assert entries[0].user_id == member.id


async def test_an_event_this_side_reads_nothing_of_is_ignored_and_not_processed(db, tenant, member):
    """The queue would grow forever behind a name nobody reads, and the status says which of the two happened."""
    await report(db, tenant, member, "search_performed")

    processed = await app_event_service.process_pending(db)

    assert processed[0].status == AppEventStatus.IGNORED
    assert processed[0].processed_at is not None
    assert await logs(db) == []


async def test_a_name_the_backend_never_learned_is_ignored_and_never_failed(db, tenant, member):
    """An app ships before this side does, so a name from the future is nothing to read rather than a failure."""
    await report(db, tenant, member, "something_a_newer_app_reports")

    processed = await app_event_service.process_pending(db)

    assert processed[0].status == AppEventStatus.IGNORED


async def test_a_handler_that_breaks_leaves_the_event_failed_with_what_broke(db, tenant, member, monkeypatch):
    async def explode(*args, **kwargs):
        raise RuntimeError("the log refused")

    monkeypatch.setattr(app_event_service, "dispatch", explode)

    await report(db, tenant, member, AppEventName.PRODUCT_PURCHASED)

    processed = await app_event_service.process_pending(db)

    assert processed[0].status == AppEventStatus.FAILED
    assert processed[0].error_code == "RuntimeError"
    assert processed[0].error_message == "the log refused"
    assert processed[0].attempts == 1


async def test_a_pass_that_already_ran_finds_nothing_left_to_do(db, tenant, member):
    await report(db, tenant, member, "app_opened")

    assert len(await app_event_service.process_pending(db)) == 1
    assert await app_event_service.process_pending(db) == []


async def test_an_event_already_read_is_never_picked_up_again(db, tenant, member):
    event = await report(db, tenant, member, "app_opened")
    event.status = AppEventStatus.PROCESSED
    await db.commit()

    assert await app_event_service.process_pending(db) == []


async def test_what_broke_is_read_again_and_a_pass_that_worked_clears_the_error(db, tenant, member, monkeypatch):
    """The queue keeps the same net the grant, the webhook event and the mail queue have."""

    async def explode(*args, **kwargs):
        raise RuntimeError("the log refused")

    monkeypatch.setattr(app_event_service, "dispatch", explode)
    await report(db, tenant, member, AppEventName.PRODUCT_PURCHASED)

    assert (await app_event_service.process_pending(db))[0].status == AppEventStatus.FAILED

    monkeypatch.undo()

    settled = (await app_event_service.process_pending(db))[0]

    assert settled.status == AppEventStatus.PROCESSED
    assert settled.attempts == 2
    assert (settled.error_code, settled.error_message) == (None, None)
    assert len(await logs(db)) == 1


async def test_an_event_that_keeps_breaking_stops_holding_a_slot_of_every_pass(db, tenant, member, monkeypatch):
    async def explode(*args, **kwargs):
        raise RuntimeError("the log refused")

    monkeypatch.setattr(app_event_service, "dispatch", explode)

    event = await report(db, tenant, member, AppEventName.PRODUCT_PURCHASED)

    for attempt in range(MAX_ATTEMPTS):
        assert len(await app_event_service.process_pending(db)) == 1, f"attempt {attempt + 1} should still be read"

    assert await app_event_service.process_pending(db) == []
    assert event.attempts == MAX_ATTEMPTS


async def test_a_pass_never_takes_more_than_its_batch(db, tenant, member, monkeypatch):

    monkeypatch.setattr(services_app_event_service_module, "BATCH", 2)

    for index in range(3):
        await report(db, tenant, member, f"app_opened-{index}")

    assert len(await app_event_service.process_pending(db)) == 2


async def test_a_batch_the_app_sent_twice_at_once_is_accepted_once(db, tenant, member, monkeypatch):
    """The UUID is what makes a resent batch enter once, and reading before writing does not hold that up under concurrency."""
    original = type(app_event_service).known_uuids
    missed = []

    async def blind_once(self, session, uuids):
        if missed:
            return await original(self, session, uuids)

        missed.append(True)

        session.add(AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="repetido", name="app_opened", params={}, occurred_at=now(), status=AppEventStatus.PENDING))
        await session.commit()

        return set()

    monkeypatch.setattr(type(app_event_service), "known_uuids", blind_once)

    accepted, duplicated = await app_event_service.ingest(db, tenant, member, [{"uuid": "repetido", "name": "app_opened", "params": {}, "occurred_at": now()}])

    assert (accepted, duplicated) == (0, 1)
    assert len((await db.execute(select(AppEvent))).scalars().all()) == 1


async def test_an_event_is_taken_before_it_is_read_so_two_passes_never_read_it_twice(db, tenant, member):
    """The pass is allowed to run almost as long as the interval, so the next one starts on another node while this one is still going."""
    from services.app_event_service import app_event_service

    record = AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="taken-once", name="content-viewed", params={}, occurred_at=now(), status=AppEventStatus.PENDING)
    db.add(record)
    await db.commit()

    assert await app_event_service.claim(db, record.id) is True
    assert await app_event_service.claim(db, record.id) is False

    await db.refresh(record)

    assert record.status is AppEventStatus.PROCESSING
    assert record.attempts == 1


async def test_an_event_a_dead_pass_left_taken_is_read_again(db, tenant, member):
    """A node that died mid-pass leaves the row taken, and nothing would ever read it again without the window."""
    from datetime import timedelta

    from services.app_event_service import app_event_service
    from services.delivery_service import ABANDONED_AFTER

    record = AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="left-behind", name="content-viewed", params={}, occurred_at=now(), status=AppEventStatus.PROCESSING, updated_at=now() - ABANDONED_AFTER - timedelta(minutes=1))
    db.add(record)
    await db.commit()

    worked = await app_event_service.process_pending(db)

    assert [event.uuid for event in worked] == ["left-behind"]
    assert worked[0].status is AppEventStatus.PROCESSED


async def test_an_event_whose_last_attempt_died_is_closed_as_failed(db, tenant, member):
    """Past its attempts no pass reads it again, and retention only reaches what closed."""
    from datetime import timedelta

    from services.app_event_service import MAX_ATTEMPTS, app_event_service
    from services.delivery_service import ABANDONED_AFTER

    record = AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="spent", name="content-viewed", params={}, occurred_at=now(), status=AppEventStatus.PROCESSING, attempts=MAX_ATTEMPTS, updated_at=now() - ABANDONED_AFTER - timedelta(minutes=1))
    db.add(record)
    await db.commit()

    assert await app_event_service.close_exhausted(db) == 1

    await db.refresh(record)

    assert (record.status, record.error_code) == (AppEventStatus.FAILED, "abandoned")
    assert await app_event_service.process_pending(db) == []


async def test_an_event_another_pass_already_took_is_left_alone_and_the_rest_are_read(db, tenant, member, monkeypatch):
    """The row is selected and then claimed, and whoever loses the claim moves on instead of working it a second time."""
    from services.app_event_service import app_event_service

    for name in ("taken-elsewhere", "still-ours"):
        db.add(AppEvent(tenant_id=tenant.id, user_id=member.id, uuid=name, name=AppEventName.CONTENT_VIEWED, params={}, occurred_at=now(), status=AppEventStatus.PENDING))

    await db.commit()

    taking = app_event_service.claim

    async def lose_the_first(session, record_id):
        return False if (await session.get(AppEvent, record_id)).uuid == "taken-elsewhere" else await taking(session, record_id)

    monkeypatch.setattr(app_event_service, "claim", lose_the_first)

    worked = await app_event_service.process_pending(db)

    assert [event.uuid for event in worked] == ["still-ours"]


async def test_a_rolled_back_handler_does_not_stop_the_rest_of_the_event_batch(db, tenant, member, monkeypatch):
    from sqlalchemy.exc import OperationalError

    events = [await report(db, tenant, member, AppEventName.PRODUCT_PURCHASED) for _ in range(3)]
    failing_uuid = events[1].uuid
    dispatch = app_event_service.dispatch

    async def interrupted(session, event):
        if event.uuid == failing_uuid:
            await session.execute(select(1))
            await session.rollback()

            raise OperationalError("INSERT", {}, RuntimeError("database connection interrupted"))

        return await dispatch(session, event)

    monkeypatch.setattr(app_event_service, "dispatch", interrupted)

    processed = await app_event_service.process_pending(db)

    assert [event.status for event in processed] == [AppEventStatus.PROCESSED, AppEventStatus.FAILED, AppEventStatus.PROCESSED]
    assert processed[1].error_code == "OperationalError"
    assert processed[1].attempts == 1
    assert len(await logs(db)) == 2


async def test_an_event_and_its_audit_entry_are_rolled_back_together(db, tenant, member, monkeypatch):
    await report(db, tenant, member, AppEventName.PRODUCT_PURCHASED)
    dispatch = app_event_service.dispatch

    async def interrupted(session, event):
        await dispatch(session, event)
        await session.flush()

        raise RuntimeError("interrupted before completing the event")

    monkeypatch.setattr(app_event_service, "dispatch", interrupted)

    processed = await app_event_service.process_pending(db)

    assert processed[0].status == AppEventStatus.FAILED
    assert processed[0].error_code == "RuntimeError"
    assert await logs(db) == []


async def test_a_failed_event_commit_can_be_retried_without_duplicating_its_audit(db, tenant, member):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    from helpers.db import async_engine

    await report(db, tenant, member, AppEventName.PRODUCT_PURCHASED)
    failed = False

    def interrupted(connection, cursor, statement, parameters, context, executemany):
        nonlocal failed

        if statement.startswith("UPDATE app_event SET") and "processed_at" in statement and not failed:
            failed = True

            raise OperationalError(statement, parameters, RuntimeError("write interrupted"))

    event.listen(async_engine.sync_engine, "before_cursor_execute", interrupted)

    try:
        processed = await app_event_service.process_pending(db)

        assert failed
        assert processed[0].status == AppEventStatus.FAILED
        assert processed[0].error_code == "OperationalError"
        assert await logs(db) == []

        retried = await app_event_service.process_pending(db)

        assert retried[0].status == AppEventStatus.PROCESSED
        assert retried[0].attempts == 2
        assert len(await logs(db)) == 1
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", interrupted)


async def test_a_claimed_event_removed_before_it_is_read_is_skipped(db, tenant, member, monkeypatch):
    from sqlalchemy import delete

    event = await report(db, tenant, member, AppEventName.PRODUCT_PURCHASED)
    record_id = event.id
    claim = app_event_service.claim

    async def removed(session, identifier):
        claimed = await claim(session, identifier)
        await session.execute(delete(AppEvent).where(AppEvent.id == identifier))
        await session.commit()

        return claimed

    monkeypatch.setattr(app_event_service, "claim", removed)

    assert await app_event_service.process_pending(db) == []
    assert await db.get(AppEvent, record_id) is None


async def test_an_event_removed_during_a_failed_attempt_is_not_recreated(db, tenant, member, monkeypatch):
    from sqlalchemy import delete

    from helpers.db import AsyncSessionLocal

    event = await report(db, tenant, member, AppEventName.PRODUCT_PURCHASED)
    record_id = event.id

    async def removed(session, record):
        await session.execute(select(1))

        async with AsyncSessionLocal() as deleting:
            await deleting.execute(delete(AppEvent).where(AppEvent.id == record_id))
            await deleting.commit()

        raise RuntimeError("the owner removed this event")

    monkeypatch.setattr(app_event_service, "dispatch", removed)

    assert await app_event_service.process_pending(db) == []
    assert await db.get(AppEvent, record_id) is None
