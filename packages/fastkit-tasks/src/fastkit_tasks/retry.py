from enum import Enum


class RetryPolicy(str, Enum):
    fixed = "fixed"
    linear = "linear"
    exponential = "exponential"
    exponential_jitter = "exponential_jitter"


def compute_delay(
    policy: RetryPolicy, base_delay: int, attempt: int, jitter_source: float = 0.0
) -> int:
    """Return the delay in seconds before the given attempt number under a policy."""

    if policy is RetryPolicy.fixed:
        return base_delay

    if policy is RetryPolicy.linear:
        return base_delay * attempt

    exponential = base_delay * (2 ** (attempt - 1))

    if policy is RetryPolicy.exponential:
        return exponential

    jitter = int(exponential * jitter_source)

    return exponential + jitter
