class PermanentTaskError(Exception):
    """Raised by a handler to signal a non-retryable failure."""
