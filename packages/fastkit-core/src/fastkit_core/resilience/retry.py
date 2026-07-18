import asyncio
import logging
import random

from fastkit_core.resilience.circuit_breaker import CircuitBreaker
from fastkit_core.resilience.circuit_open_error import CircuitOpenError
from fastkit_core.resilience.retry_policy import RetryPolicy

logger = logging.getLogger("fastkit.resilience")


async def run_with_retry(
    operation,
    policy: RetryPolicy | None = None,
    *,
    breaker: CircuitBreaker | None = None,
    sleep=asyncio.sleep,
    jitter_source=random.random,
    name: str = "operation",
):
    """Run an async operation with retries, exponential backoff and an optional circuit breaker.

    Failures are logged. When a breaker is supplied it records outcomes and rejects calls
    while open, letting a recovered dependency reconnect on the next half-open probe.
    """

    policy = policy or RetryPolicy()
    attempt = 0

    while True:
        attempt += 1

        if breaker is not None and not breaker.allow():
            raise CircuitOpenError(f"{name} circuit is open")

        try:
            result = await operation()
        except policy.retry_on as error:
            if breaker is not None:
                breaker.record_failure()

            if attempt >= policy.max_attempts:
                logger.warning("%s failed after %d attempts: %s", name, attempt, error)

                raise

            delay = policy.delay_for(attempt, jitter_source())
            logger.info(
                "%s failed on attempt %d/%d, retrying in %.2fs: %s",
                name,
                attempt,
                policy.max_attempts,
                delay,
                error,
            )
            await sleep(delay)
        else:
            if breaker is not None:
                breaker.record_success()

            return result
