from datetime import timedelta

from fastkit_tasks.models import ExecutionStatus, TaskExecution
from fastkit_tasks.queue import TaskQueue
from fastkit_tasks.registry import TaskDefinition
from fastkit_tasks.retry import RetryPolicy


async def test_enqueue_applies_registered_task_policy(database, clock, registry):
    async def handler(**kwargs):
        return None

    registry.register(TaskDefinition(name="reports.build", handler=handler, queue="reports", max_attempts=5, timeout=300, retry_delay=30))
    queue = TaskQueue(database.session_factory, registry=registry, clock=clock)

    execution = await queue.enqueue("reports.build", queue="reports")

    assert execution.max_attempts == 5
    assert execution.timeout_seconds == 300
    assert execution.retry_delay_seconds == 30

    override = await queue.enqueue("reports.build", queue="reports", max_attempts=1)

    assert override.max_attempts == 1


async def test_enqueue_creates_pending(queue):
    execution = await queue.enqueue("emails.send", payload={"to": "a@b.c"}, queue="email", max_attempts=3)

    assert execution.status == ExecutionStatus.pending.value
    assert execution.payload == {"to": "a@b.c"}
    assert execution.queue == "email"


async def test_idempotency_returns_existing(queue):
    first = await queue.enqueue("emails.send", idempotency_key="key-1")
    second = await queue.enqueue("emails.send", idempotency_key="key-1")

    assert first.id == second.id


async def test_lease_marks_running(queue):
    await queue.enqueue("emails.send", queue="email")

    leased = await queue.lease("worker-1", ["email"])

    assert leased is not None
    assert leased.status == ExecutionStatus.running.value
    assert leased.locked_by == "worker-1"
    assert leased.attempt_count == 1


async def test_lease_skips_future_tasks(queue, clock):
    await queue.enqueue("emails.send", queue="email", available_at=clock() + timedelta(seconds=60))

    assert await queue.lease("worker-1", ["email"]) is None


async def test_second_worker_cannot_release(queue):
    await queue.enqueue("emails.send", queue="email")

    first = await queue.lease("worker-1", ["email"])
    second = await queue.lease("worker-2", ["email"])

    assert first is not None
    assert second is None


async def test_complete(queue):
    execution = await queue.enqueue("emails.send", queue="email")
    await queue.lease("worker-1", ["email"])

    await queue.complete(execution.id, "worker-1", {"sent": True})

    async with queue._session_factory() as session:
        stored = await session.get(TaskExecution, execution.id)

    assert stored.status == ExecutionStatus.succeeded.value
    assert stored.result == {"sent": True}
    assert stored.progress == 100


async def test_fail_retries_then_exhausts(queue):
    execution = await queue.enqueue("emails.send", queue="email", max_attempts=2, retry_delay=0)

    await queue.lease("worker-1", ["email"])
    status = await queue.fail(execution.id, "worker-1", "task.error", "boom", retry_policy=RetryPolicy.fixed)
    assert status == ExecutionStatus.retrying.value

    await queue.lease("worker-1", ["email"])
    status = await queue.fail(execution.id, "worker-1", "task.error", "boom again")
    assert status == ExecutionStatus.failed.value


async def test_lease_skips_locked_candidate(queue, clock):
    async with queue._session_factory() as session:
        session.add(
            TaskExecution(
                task_name="emails.send",
                queue="email",
                status=ExecutionStatus.pending.value,
                priority=10,
                available_at=clock(),
                locked_until=clock() + timedelta(seconds=100),
            )
        )
        session.add(TaskExecution(task_name="emails.send", queue="email", status=ExecutionStatus.pending.value, priority=0, available_at=clock()))
        await session.commit()

    leased = await queue.lease("worker-1", ["email"])

    assert leased is not None
    assert leased.priority == 0


async def test_fail_non_retryable(queue):
    execution = await queue.enqueue("emails.send", queue="email", max_attempts=5)
    await queue.lease("worker-1", ["email"])

    status = await queue.fail(execution.id, "worker-1", "task.permanent", "nope", retryable=False)

    assert status == ExecutionStatus.failed.value


async def test_stale_worker_cannot_finalize_a_reclaimed_execution(queue, clock):
    execution = await queue.enqueue("emails.send", queue="email", max_attempts=3)
    await queue.lease("worker-1", ["email"], lease_seconds=30)

    clock.advance(120)
    await queue.reclaim_expired()
    await queue.lease("worker-2", ["email"])

    assert await queue.complete(execution.id, "worker-1", {"stale": True}) is False
    assert await queue.fail(execution.id, "worker-1", "task.error", "stale") is None

    async with queue._session_factory() as session:
        stored = await session.get(TaskExecution, execution.id)

    assert stored.status == ExecutionStatus.running.value
    assert stored.locked_by == "worker-2"


async def test_cancel(queue):
    execution = await queue.enqueue("emails.send", queue="email")

    assert await queue.cancel(execution.id) is True
    assert await queue.cancel(execution.id) is False


async def test_heartbeat_updates_progress(queue):
    execution = await queue.enqueue("emails.send", queue="email")
    await queue.lease("worker-1", ["email"])

    assert await queue.heartbeat(execution.id, "worker-1", progress=50, message="halfway") is True
    assert await queue.heartbeat(execution.id, "worker-2") is False

    async with queue._session_factory() as session:
        stored = await session.get(TaskExecution, execution.id)

    assert stored.progress == 50
    assert stored.progress_message == "halfway"


async def test_reclaim_expired_lease_retries_when_under_budget(queue, clock):
    execution = await queue.enqueue("emails.send", queue="email", max_attempts=3)
    await queue.lease("worker-1", ["email"], lease_seconds=30)

    clock.advance(120)
    reclaimed = await queue.reclaim_expired()

    assert reclaimed == 1

    async with queue._session_factory() as session:
        stored = await session.get(TaskExecution, execution.id)

    assert stored.status == ExecutionStatus.retrying.value


async def test_reclaim_expired_lease_fails_a_one_shot_task(queue, clock):
    execution = await queue.enqueue("emails.send", queue="email")
    await queue.lease("worker-1", ["email"], lease_seconds=30)

    clock.advance(120)
    reclaimed = await queue.reclaim_expired()

    assert reclaimed == 1

    async with queue._session_factory() as session:
        stored = await session.get(TaskExecution, execution.id)

    assert stored.status == ExecutionStatus.failed.value
    assert stored.finished_at is not None
