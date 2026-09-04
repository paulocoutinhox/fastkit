from datetime import datetime, timedelta, timezone

import pytest
from queuefy.run import Run
from queuefy.task import Task
from queuefy.worker import Worker
from sqlalchemy import select

from enums.system_log import LogCategory, LogLevel
from helpers import scheduler
from helpers.settings import settings
from models.system_log import SystemLog


def a_run(name: str = "run_subscription_cycle", **overrides) -> Run:
    return Run(**{"name": name, "queue": "subscription", "attempts": 1} | overrides)


async def entries(db) -> list[SystemLog]:
    return list((await db.execute(select(SystemLog).order_by(SystemLog.id))).scalars())


def test_every_job_of_the_application_is_declared_on_the_queue():
    import jobs.email  # noqa: F401
    import jobs.event  # noqa: F401
    import jobs.retention  # noqa: F401
    import jobs.storage  # noqa: F401
    import jobs.subscription  # noqa: F401

    assert set(scheduler.app.tasks) == {"run_subscription_cycle", "send_pending_emails", "process_pending_events", "discard_orphan_files", "discard_expired_records"}


def test_every_job_carries_a_cron_and_a_queue_of_its_own():
    """Two jobs sharing a queue would let one instance be given work it was not meant to have."""
    declared = scheduler.app.tasks.values()

    assert all(task.trigger is not None for task in declared)
    assert len({task.queue for task in declared}) == len(scheduler.app.tasks)


def test_an_instance_without_queues_serves_every_one_its_jobs_declare(monkeypatch):
    monkeypatch.setattr(settings, "cron_queues", [])

    assert scheduler.served_queues() == ("email", "event", "retention", "storage", "subscription")


def test_an_instance_serves_only_the_queues_it_was_given(monkeypatch):
    monkeypatch.setattr(settings, "cron_queues", ["storage"])

    assert scheduler.served_queues() == ("storage",)


def test_the_worker_is_built_over_the_same_queue_the_jobs_were_declared_on(monkeypatch):
    monkeypatch.setattr(settings, "cron_queues", ["email"])

    worker = scheduler.build_worker()

    assert isinstance(worker, Worker)
    assert worker.app is scheduler.app
    assert worker.queues == ("email",)
    assert (worker.concurrency, worker.poll) == (settings.cron_concurrency, settings.cron_poll_seconds)
    assert worker.lease == timedelta(seconds=settings.cron_lease_seconds)


def test_the_lease_gives_the_heartbeat_room_to_breathe_under_load():
    """A claim held for a minute with a heartbeat every twenty seconds is tight for a process serving requests too."""
    worker = scheduler.build_worker()

    assert worker.lease >= timedelta(minutes=5)


def test_a_worker_is_built_listening_on_every_stage():
    worker = scheduler.build_worker()

    assert [listener.__name__ for listener in worker.starting] == ["started"]
    assert [listener.__name__ for listener in worker.finishing] == ["finished"]
    assert [listener.__name__ for listener in worker.failing] == ["failed"]


async def test_a_run_that_started_leaves_a_line_saying_so(db):
    await scheduler.started(a_run())

    written = (await entries(db))[0]

    assert (written.level, written.category) == (LogLevel.INFO, LogCategory.CRON)
    assert written.meta == {"job": "run_subscription_cycle", "attempt": 1}


async def test_a_run_that_finished_leaves_how_long_it_took(db):
    await scheduler.finished(a_run(), None, 1.2345)

    written = (await entries(db))[0]

    assert written.level == LogLevel.SUCCESS
    assert written.meta == {"job": "run_subscription_cycle", "duration": 1.234}


@pytest.mark.parametrize("retrying", [True, False])
async def test_a_run_that_broke_leaves_what_broke_and_whether_it_comes_back(db, retrying):
    await scheduler.failed(a_run(), RuntimeError("boom"), 0.5, retrying)

    written = (await entries(db))[0]

    assert written.level == LogLevel.ERROR
    assert written.meta == {"job": "run_subscription_cycle", "duration": 0.5, "error": "boom", "retrying": retrying}


async def test_the_audit_trail_is_written_by_the_worker_and_not_by_the_job(db):
    """The job body knows nothing about system_log, and the run still leaves a start and a finish behind."""
    worker = scheduler.build_worker()
    ran = []

    scheduler.app.register(Task(name="probe", handler=lambda: ran.append(1), queue="probe"))

    try:
        await scheduler.app.setup()
        written = await scheduler.app.enqueue("probe")
        worker.queues = ("probe",)

        await worker.run_once()
        await worker.drain()
    finally:
        del scheduler.app.tasks["probe"]

    assert ran == [1]
    assert [row.level for row in await entries(db)] == [LogLevel.INFO, LogLevel.SUCCESS]
    assert (await scheduler.app.get(written.id)).name == "probe"


def test_no_pass_is_allowed_to_run_into_the_window_of_the_next_one():
    """A subscription pass paces its calls to the provider to fit five minutes, and two of them at once would spend that budget twice."""
    moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    offenders = []

    for task in scheduler.app.tasks.values():
        first = task.trigger.next_after(moment)
        period = (task.trigger.next_after(first) - first).total_seconds()

        if task.timeout is None or task.timeout >= period:
            offenders.append((task.name, task.timeout, period))

    assert offenders == [], "a job with no timeout, or one longer than its own period, may overlap itself"


async def test_the_trail_says_what_ran_and_not_only_its_name(db):
    """A row reading `send_pending_emails finished` says nothing about what that name is, and the trail is read by whoever was not there."""
    from sqlalchemy import select

    from models.system_log import SystemLog

    await scheduler.finished(Run(id="1", name="send_pending_emails", queue="email", payload={}), None, 0.5)

    written = await db.scalar(select(SystemLog.description).order_by(SystemLog.id.desc()))

    assert written == 'Scheduled service "send_pending_emails" finished'
