# fastkit-tasks

Persistent task queue and scheduler for FastKit. Tasks survive restarts and are
never lost.

## Installation

```bash
pip install fastkit-tasks
```

## Registry

```python
@registry.task("emails.send", queue="email", max_attempts=5, timeout=60)
async def send_email_task(context, payload):
    await context.heartbeat(progress=50)
    ...
```

Task names are stable identifiers, never import paths.

## Queue and leasing

`TaskQueue` enqueues `TaskExecution` rows and leases them with a portable,
contention-safe conditional `UPDATE` (status + availability + lease guard) so two
workers never run the same execution. Supports idempotency keys, heartbeat,
progress, retry, cancel and expired-lease reclaim.

## Worker

`Worker.run_once` leases one execution, runs the handler under its timeout, and
records a `TaskAttempt`. Handlers raise `PermanentTaskError` for non-retryable
failures; timeouts and generic errors are retried per policy (`fixed`, `linear`,
`exponential`, `exponential_jitter`).

## Scheduler

`Scheduler.tick` materializes due `ScheduledTask` rows into queued executions,
using a unique `(scheduled_task_id, scheduled_for)` slot so two schedulers
produce a single occurrence. `once` disables after running, `interval` and `cron`
compute the next run.

## Testing

100% branch coverage, including duplicate-worker leasing, retry exhaustion,
timeout, idempotency, cron scheduling and duplicate-slot safety.

```bash
pytest packages/fastkit-tasks --cov=fastkit_tasks --cov-branch
```
