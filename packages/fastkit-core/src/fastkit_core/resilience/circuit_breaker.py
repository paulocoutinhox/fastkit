import time

from fastkit_core.resilience.circuit_state import CircuitState


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
