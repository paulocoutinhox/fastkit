from dataclasses import dataclass


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
