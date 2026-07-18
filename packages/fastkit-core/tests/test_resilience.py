import pytest

from fastkit_core.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    RetryPolicy,
    run_with_retry,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


async def _noop_sleep(_seconds):
    return None


def test_retry_policy_backoff_and_cap():
    policy = RetryPolicy(base_delay=1.0, multiplier=2.0, max_delay=5.0, jitter=0.5)

    assert policy.delay_for(1, 0.0) == 1.0
    assert policy.delay_for(2, 0.0) == 2.0
    # capped at max_delay, then jitter added on top
    assert policy.delay_for(10, 0.0) == 5.0
    assert policy.delay_for(10, 1.0) == 5.0 + 2.5


async def test_run_with_retry_succeeds_first_try():
    calls = []

    async def operation():
        calls.append(1)

        return "ok"

    result = await run_with_retry(operation, sleep=_noop_sleep)

    assert result == "ok"
    assert len(calls) == 1


async def test_run_with_retry_recovers_after_failures():
    attempts = []
    delays = []

    async def operation():
        attempts.append(1)

        if len(attempts) < 3:
            raise ValueError("transient")

        return "recovered"

    async def sleep(seconds):
        delays.append(seconds)

    policy = RetryPolicy(max_attempts=3, base_delay=1.0, jitter=0.0)
    result = await run_with_retry(
        operation, policy, sleep=sleep, jitter_source=lambda: 0.0
    )

    assert result == "recovered"
    assert len(attempts) == 3
    assert delays == [1.0, 2.0]


async def test_run_with_retry_raises_after_exhaustion():
    async def operation():
        raise ValueError("always")

    policy = RetryPolicy(max_attempts=2, retry_on=(ValueError,))

    with pytest.raises(ValueError):
        await run_with_retry(
            operation, policy, sleep=_noop_sleep, jitter_source=lambda: 0.0
        )


async def test_run_with_retry_records_breaker_outcomes():
    breaker = CircuitBreaker(failure_threshold=2)
    attempts = []

    async def operation():
        attempts.append(1)

        if len(attempts) < 2:
            raise RuntimeError("down")

        return "up"

    result = await run_with_retry(
        operation,
        RetryPolicy(max_attempts=3),
        breaker=breaker,
        sleep=_noop_sleep,
        jitter_source=lambda: 0.0,
    )

    assert result == "up"
    assert breaker.state is CircuitState.closed


async def test_run_with_retry_rejects_when_circuit_open():
    breaker = CircuitBreaker(failure_threshold=1, reset_after_seconds=100)
    breaker.record_failure()

    async def operation():
        raise AssertionError("must not run while open")

    with pytest.raises(CircuitOpenError):
        await run_with_retry(operation, breaker=breaker, sleep=_noop_sleep)


def test_circuit_breaker_opens_and_half_opens():
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=2, reset_after_seconds=30, clock=clock)

    assert breaker.allow() is True

    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.open
    assert breaker.allow() is False

    clock.advance(30)
    assert breaker.allow() is True
    assert breaker.state is CircuitState.half_open

    breaker.record_success()
    assert breaker.state is CircuitState.closed
