import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import select

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_tasks.app import TasksApp
from fastkit_tasks.models import (
    ExecutionStatus,
    ScheduledTask,
    ScheduleType,
    TaskAttempt,
    TaskExecution,
)
from fastkit_tasks.queue import TaskQueue
from fastkit_tasks.registry import PermanentTaskError, TaskRegistry
from fastkit_tasks.scheduler import Scheduler, _aware
from fastkit_tasks.worker import Worker


def worker_for(queue, registry, database, clock):
    return Worker(
        queue, registry, database, worker_id="w1", queues=["default"], clock=clock
    )


async def test_worker_runs_task_successfully(queue, registry, database, clock):
    executed = {}

    @registry.task("do.work")
    async def handler(context, payload):
        executed["payload"] = payload
        await context.heartbeat(progress=50)

        return {"ok": True}

    execution = await queue.enqueue("do.work", payload={"x": 1})
    status = await worker_for(queue, registry, database, clock).run_once()

    assert status == "succeeded"
    assert executed["payload"] == {"x": 1}

    async with database.session_factory() as session:
        stored = await session.get(TaskExecution, execution.id)
        attempts = (await session.execute(select(TaskAttempt))).scalars().all()

    assert stored.status == ExecutionStatus.succeeded.value
    assert attempts[0].status == "succeeded"


async def test_worker_returns_none_when_empty(queue, registry, database, clock):
    assert await worker_for(queue, registry, database, clock).run_once() is None


async def test_worker_extends_lease_to_cover_a_long_timeout(
    queue, registry, database, clock
):
    seen = {}

    @registry.task("long.work")
    async def handler(context, payload):
        async with database.session_factory() as session:
            stored = await session.get(TaskExecution, context.execution.id)
            seen["locked_until"] = stored.locked_until

    await queue.enqueue("long.work", timeout=300)
    started = clock().replace(tzinfo=None)
    await worker_for(queue, registry, database, clock).run_once()

    # the lease covers the full timeout (300s) plus the base lease grace (60s)
    locked_until = seen["locked_until"].replace(tzinfo=None)
    assert (locked_until - started).total_seconds() >= 300


async def test_worker_retries_on_error(queue, registry, database, clock):
    @registry.task("flaky", max_attempts=2)
    async def handler(context, payload):
        raise RuntimeError("boom")

    await queue.enqueue("flaky", max_attempts=2)
    status = await worker_for(queue, registry, database, clock).run_once()

    assert status == ExecutionStatus.retrying.value


async def test_worker_fails_unregistered_task_without_retry(
    queue, registry, database, clock
):
    await queue.enqueue("ghost.task", max_attempts=5)
    status = await worker_for(queue, registry, database, clock).run_once()

    assert status == ExecutionStatus.failed.value


async def test_worker_permanent_failure(queue, registry, database, clock):
    @registry.task("bad")
    async def handler(context, payload):
        raise PermanentTaskError("do not retry")

    await queue.enqueue("bad", max_attempts=5)
    status = await worker_for(queue, registry, database, clock).run_once()

    assert status == ExecutionStatus.failed.value


async def test_worker_timeout(queue, registry, database, clock):
    @registry.task("slow", max_attempts=2)
    async def handler(context, payload):
        await asyncio.sleep(1)

    await queue.enqueue("slow", timeout=0, max_attempts=2)
    status = await worker_for(queue, registry, database, clock).run_once()

    assert status == ExecutionStatus.retrying.value


async def test_worker_drain_materializes_and_runs(queue, registry, database, clock):
    done = {}

    @registry.task("beat.work")
    async def handler(context, payload):
        done["ran"] = True
        return {"ok": True}

    scheduler = Scheduler(database, queue, clock=clock)
    await _make_scheduled(
        database,
        clock,
        name="beat",
        task_name="beat.work",
        schedule_type=ScheduleType.interval.value,
        interval_seconds=60,
    )

    await worker_for(queue, registry, database, clock).drain(scheduler)

    assert done.get("ran") is True

    async with database.session_factory() as session:
        execution = (await session.execute(select(TaskExecution))).scalars().one()

    assert execution.status == ExecutionStatus.succeeded.value


async def test_worker_run_loop_processes_then_cancels(queue, registry, database, clock):
    processed = {}

    @registry.task("loop.work")
    async def handler(context, payload):
        processed["ran"] = True
        return {"ok": True}

    await queue.enqueue("loop.work")
    task = asyncio.create_task(
        worker_for(queue, registry, database, clock).run(poll_interval=0.01)
    )

    for _ in range(100):
        await asyncio.sleep(0.01)
        if processed.get("ran"):
            break

    assert processed.get("ran") is True

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_success_is_not_undone_by_a_failing_attempt_record(
    queue, registry, database, clock, monkeypatch
):
    @registry.task("ok.work")
    async def handler(context, payload):
        return {"ok": True}

    execution = await queue.enqueue("ok.work")
    worker = worker_for(queue, registry, database, clock)

    async def boom(*args, **kwargs):
        raise RuntimeError("attempt table down")

    monkeypatch.setattr(worker, "_record_attempt", boom)

    with pytest.raises(RuntimeError):
        await worker.run_once()

    async with database.session_factory() as session:
        stored = await session.get(TaskExecution, execution.id)

    assert stored.status == ExecutionStatus.succeeded.value


async def test_worker_run_loop_survives_a_cycle_error(queue, registry, database, clock):
    class _BoomScheduler:
        async def tick(self):
            raise RuntimeError("scheduler down")

    task = asyncio.create_task(
        worker_for(queue, registry, database, clock).run(
            poll_interval=0.01, scheduler=_BoomScheduler()
        )
    )
    await asyncio.sleep(0.05)

    assert not task.done()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_scheduler_transient_enqueue_error_does_not_drop_the_slot(
    database, clock
):
    class _BoomQueue:
        async def enqueue(self, **kwargs):
            raise RuntimeError("database unavailable")

    scheduler = Scheduler(database, _BoomQueue(), clock=clock)
    task = await _make_scheduled(
        database,
        clock,
        name="beat",
        task_name="do.work",
        schedule_type=ScheduleType.interval.value,
        interval_seconds=60,
    )
    original_next = _aware(task.next_run_at)

    assert await scheduler.tick() == 0

    async with database.session_factory() as session:
        stored = await session.get(ScheduledTask, task.id)

    assert _aware(stored.next_run_at) == original_next


async def _make_scheduled(database, clock, **kwargs):
    async with database.session_factory() as session:
        task = ScheduledTask(next_run_at=clock(), enabled=True, **kwargs)
        session.add(task)
        await session.commit()
        await session.refresh(task)

        return task


async def test_scheduler_materializes_interval(queue, database, clock):
    scheduler = Scheduler(database, queue, clock=clock)
    await _make_scheduled(
        database,
        clock,
        name="beat",
        task_name="do.work",
        schedule_type=ScheduleType.interval.value,
        interval_seconds=60,
    )

    count = await scheduler.tick()
    assert count == 1

    async with database.session_factory() as session:
        executions = (await session.execute(select(TaskExecution))).scalars().all()
        task = (await session.execute(select(ScheduledTask))).scalars().one()

    assert len(executions) == 1
    assert _aware(task.next_run_at) > clock()
    assert task.last_run_at is not None


async def test_scheduler_once_disables(queue, database, clock):
    scheduler = Scheduler(database, queue, clock=clock)
    await _make_scheduled(
        database,
        clock,
        name="single",
        task_name="do.work",
        schedule_type=ScheduleType.once.value,
    )

    await scheduler.tick()

    async with database.session_factory() as session:
        task = (await session.execute(select(ScheduledTask))).scalars().one()

    assert task.enabled is False
    assert task.next_run_at is None


async def test_scheduler_cron(queue, database, clock):
    scheduler = Scheduler(database, queue, clock=clock)
    await _make_scheduled(
        database,
        clock,
        name="cronjob",
        task_name="do.work",
        schedule_type=ScheduleType.cron.value,
        cron_expression="0 * * * *",
    )

    await scheduler.tick()

    async with database.session_factory() as session:
        task = (await session.execute(select(ScheduledTask))).scalars().one()

    assert task.next_run_at.minute == 0


async def test_scheduler_disables_a_task_with_an_invalid_cron(queue, database, clock):
    scheduler = Scheduler(database, queue, clock=clock)
    await _make_scheduled(
        database,
        clock,
        name="broken",
        task_name="do.work",
        schedule_type=ScheduleType.cron.value,
        cron_expression="not a cron",
    )

    await scheduler.tick()

    async with database.session_factory() as session:
        task = (await session.execute(select(ScheduledTask))).scalars().one()

    assert task.enabled is False
    assert task.next_run_at is None


async def test_scheduler_duplicate_slot_is_safe(queue, database, clock):
    scheduler = Scheduler(database, queue, clock=clock)
    task = await _make_scheduled(
        database,
        clock,
        name="dup",
        task_name="do.work",
        schedule_type=ScheduleType.interval.value,
        interval_seconds=60,
    )

    # pre-create the execution for this exact slot so the scheduler hits the unique constraint
    await queue.enqueue(
        "do.work",
        scheduled_task_id=task.id,
        scheduled_for=clock(),
        available_at=clock(),
    )

    materialized = await scheduler.tick()

    assert materialized == 0

    async with database.session_factory() as session:
        executions = (await session.execute(select(TaskExecution))).scalars().all()

    assert len(executions) == 1


async def test_scheduler_skips_disabled(queue, database, clock):
    scheduler = Scheduler(database, queue, clock=clock)

    async with database.session_factory() as session:
        session.add(
            ScheduledTask(
                name="off",
                task_name="do.work",
                schedule_type=ScheduleType.once.value,
                next_run_at=clock(),
                enabled=False,
            )
        )
        await session.commit()

    assert await scheduler.tick() == 0


class Settings:
    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        pool_recycle = 1800
        echo = False

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.tasks"]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {
            "fastkit.core": CoreApp,
            "fastkit.db": DbApp,
            "fastkit.tasks": TasksApp,
        },
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_tasks_app_registers(runtime):
    assert TaskExecution in runtime.models.all()
    assert isinstance(runtime.component("task_queue"), TaskQueue)
    assert isinstance(runtime.component("task_registry"), TaskRegistry)


def test_registry_queues():
    registry = TaskRegistry()

    assert registry.queues() == ["default"]

    registry.task("a")(lambda context, payload: None)
    registry.task("b", queue="emails")(lambda context, payload: None)

    assert registry.queues() == ["default", "emails"]


def _worker_settings(tmp_path, run_worker, worker_queues, poll=0.01):
    class _Settings:
        class database:
            url = f"sqlite+aiosqlite:///{tmp_path}/app.db"
            pool_pre_ping = True
            pool_recycle = 1800
            echo = False

        class tasks:
            pass

        installed_apps = ["fastkit.core", "fastkit.db", "fastkit.tasks"]

    _Settings.tasks.run_worker = run_worker
    _Settings.tasks.worker_id = "test-worker"
    _Settings.tasks.worker_queues = worker_queues
    _Settings.tasks.worker_lease_seconds = 60
    _Settings.tasks.poll_interval_seconds = poll

    return _Settings


async def _bootstrapped_runtime(monkeypatch, settings):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {
            "fastkit.core": CoreApp,
            "fastkit.db": DbApp,
            "fastkit.tasks": TasksApp,
        },
    )
    runtime = Runtime(settings=settings(), installed_apps=list(settings.installed_apps))
    runtime.bootstrap()

    from fastkit_db.base import Base

    await runtime.component("database").create_all(Base.metadata)

    return runtime


async def test_tasks_app_does_not_run_worker_when_disabled(monkeypatch, tmp_path):
    runtime = await _bootstrapped_runtime(
        monkeypatch, _worker_settings(tmp_path, run_worker=False, worker_queues=None)
    )

    await runtime.start()
    await runtime.stop()


async def test_tasks_app_runs_in_process_worker_when_enabled(monkeypatch, tmp_path):
    runtime = await _bootstrapped_runtime(
        monkeypatch, _worker_settings(tmp_path, run_worker=True, worker_queues=None)
    )
    ran = {}

    runtime.component("task_registry").task("app.work")(
        lambda context, payload: ran.setdefault("ok", True)
    )
    await runtime.component("task_queue").enqueue("app.work")

    await runtime.start()

    for _ in range(100):
        await asyncio.sleep(0.02)
        if ran.get("ok"):
            break

    await runtime.stop()

    assert ran.get("ok") is True


async def test_tasks_app_honours_explicit_worker_queues(monkeypatch, tmp_path):
    runtime = await _bootstrapped_runtime(
        monkeypatch,
        _worker_settings(tmp_path, run_worker=True, worker_queues=["default"]),
    )

    await runtime.start()
    await runtime.stop()
