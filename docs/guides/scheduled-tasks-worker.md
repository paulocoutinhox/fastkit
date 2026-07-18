# Scheduled tasks and the worker

## 1. Register handlers

```python
def register_tasks(self, context):
    registry = context.component("task_registry")

    @registry.task("myproject.cleanup", max_attempts=3, timeout=300)
    async def cleanup(ctx, payload):
        removed = await context.component("file_service").cleanup_orphans()
        return {"removed": removed}

    @registry.task("myproject.send_welcome_email", queue="emails")
    async def send_welcome(ctx, payload):
        ...
```

An unregistered task name fails the execution `retryable=False` (no infinite crash loop).

## 2. Enqueue work

```python
queue = context.component("task_queue")
await queue.enqueue("myproject.send_welcome_email", {"user_id": "42"})
```

The registered task's retry policy (`max_attempts`/`timeout`/`retry_delay`) is authoritative — an
explicit `enqueue` argument still wins.

## 3. Schedule recurring work

Create a `ScheduledTask` row (cron or interval):

```python
ScheduledTask(name="Nightly cleanup", task_name="myproject.cleanup",
              schedule_type="cron", cron_expression="0 3 * * *", queue="default")
```

Cron supports `*`, ranges (`9-17`), steps (`*/2`), lists and POSIX `7` as Sunday; an invalid expression
disables that schedule instead of stalling `tick()`.

## 4. Run the worker

Enqueue/schedule only persist and materialize work — a **worker must run to execute it**:

```bash
FASTKIT__TASKS__RUN_WORKER=true make dev   # the server also drains the queue
make worker                                # a standalone worker process
```

`make dev` and `make worker` set `run_worker`; tests/e2e leave it unset for determinism. See the
[tasks package](../packages/tasks.md).
