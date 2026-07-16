from datetime import datetime, timedelta, timezone


class FrozenClock:
    """A controllable clock for deterministic time in tests."""

    def __init__(self, start: datetime | None = None):
        self._now = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self._now

    def now(self) -> datetime:
        return self._now

    def tick(self, seconds: float) -> datetime:
        self._now += timedelta(seconds=seconds)

        return self._now

    def set(self, moment: datetime) -> None:
        self._now = moment
