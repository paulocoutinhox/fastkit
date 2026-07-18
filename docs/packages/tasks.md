# fastkit-tasks

A persistent task queue and scheduler with durable retry. The queue/scheduler only **persist and
materialize** work — a **`Worker` must run to execute it**.

## Register a handler

Handlers must be registered or the worker fails the execution `retryable=False` (no infinite crash
loop):

```python
def register_tasks(self, context):
    registry = context.component("task_registry")

    @registry.task("myproject.send_welcome_email", queue="emails", max_attempts=5, timeout=300)
    async def send_welcome_email(ctx, payload):
        ...
        return {"sent": True}
```

A registered task's retry policy is **authoritative**: `enqueue` fills `max_attempts`/`timeout`/
`retry_delay` from the `TaskDefinition` when the caller doesn't override them.

## The worker

- `Worker.run_once()` — lease + run one execution.
- `Worker.drain(scheduler)` — one cycle: `scheduler.tick()` → `queue.reclaim_expired()` → run every
  ready execution.
- `Worker.run(poll_interval, scheduler)` — the long-running loop (drain, sleep, repeat until
  cancelled).

**Any running server is also a worker**: `TasksApp.startup/shutdown` spawn/cancel an in-process
`Worker.run()` when `settings.tasks.run_worker` is true (`FASTKIT__TASKS__RUN_WORKER=true`). `make
worker` boots the runtime as a standalone worker process.

## Correctness (do not regress)

- Task finalization is **lease-guarded** (`complete`/`fail` write via a conditional `UPDATE … WHERE
  id=? AND locked_by=? AND status='running'`), so a worker whose lease expired can't clobber the
  worker that now legitimately holds it.
- The success path runs `complete()` + bookkeeping **outside** the handler `try`, so a bookkeeping
  failure after a genuine success can't flip it to failed (at-least-once).

## Scheduling

Cron supports `*`, ranges (`9-17`), steps (`*/2`), lists, and POSIX `7` as Sunday; day-of-month and
day-of-week use POSIX OR semantics. An invalid `cron_expression` **disables** that schedule instead of
stalling `tick()`. See [Scheduled tasks and the worker](../guides/scheduled-tasks-worker.md).
