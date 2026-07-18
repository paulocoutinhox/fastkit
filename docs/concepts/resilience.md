# Resilience

`fastkit_core.resilience` provides the primitives external IO uses to degrade gracefully, log the
failure, and recover on its own.

## Building blocks

- **`CircuitBreaker`** — opens after repeated failures, short-circuits calls while open, and
  half-opens to probe recovery.
- **`RetryPolicy`** — exponential backoff with jitter.
- **`run_with_retry(op, policy, breaker=…)`** — runs an async operation under a retry policy and an
  optional breaker.

```python
from fastkit_core.resilience import CircuitBreaker, RetryPolicy, run_with_retry

breaker = CircuitBreaker(...)
policy = RetryPolicy(max_attempts=3, base_delay=0.1)
result = await run_with_retry(lambda: call_remote(), policy, breaker=breaker)
```

## Where it is used

- The **mail service** retries transient send failures.
- The **S3 storage provider** wraps writes in the retry/breaker.

The rule: **external IO must degrade gracefully.** A dependency being down turns into a `degraded`
health status and a logged failure, never an admin-killing 500.

## Known limits

Some paths are documented follow-ups rather than silently half-done: mail counts a breaker-open
attempt; S3 reads bypass the retry/breaker. These are called out so they can be fixed with real
atomicity when needed — not worked around.
