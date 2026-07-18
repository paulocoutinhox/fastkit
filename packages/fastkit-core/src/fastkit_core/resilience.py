from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("fastkit.resilience")


class CircuitState(str, Enum):
    closed = "closed"
    open = "open"
    half_open = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because its circuit breaker is open."""


class CircuitBreaker:
    """Opens after repeated failures and half-opens after a cooldown to probe recovery."""

    def __init__(
        self, failure_threshold: int = 5, reset_after_seconds: float = 30.0, clock=None
    ):
        self._failure_threshold = failure_threshold
        self._reset_after_seconds = reset_after_seconds
        self._clock = clock or time.monotonic
        self._failures = 0
        self._opened_at: float | None = None
        self.state = CircuitState.closed

    def allow(self) -> bool:
        if self.state is CircuitState.open:
            if self._clock() - self._opened_at >= self._reset_after_seconds:
                self.state = CircuitState.half_open

                return True

            return False

        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self.state = CircuitState.closed

    def record_failure(self) -> None:
        self._failures += 1

        if self._failures >= self._failure_threshold:
            self.state = CircuitState.open
            self._opened_at = self._clock()


@dataclass
class RetryPolicy:
    """Exponential backoff with jitter and a bounded number of attempts."""

    max_attempts: int = 3
    base_delay: float = 0.1
    max_delay: float = 10.0
    multiplier: float = 2.0
    jitter: float = 0.2
    retry_on: tuple = (Exception,)

    def delay_for(self, attempt: int, jitter_source: float = 0.0) -> float:
        raw = self.base_delay * (self.multiplier ** (attempt - 1))
        capped = min(raw, self.max_delay)

        return capped + capped * self.jitter * jitter_source


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
