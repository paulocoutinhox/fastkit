from itertools import count


class Sequence:
    """Monotonic counter for generating unique values in factories."""

    def __init__(self, start: int = 1):
        self._counter = count(start)

    def next(self) -> int:
        return next(self._counter)
