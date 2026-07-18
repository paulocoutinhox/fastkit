class CircuitOpenError(Exception):
    """Raised when a call is rejected because its circuit breaker is open."""
