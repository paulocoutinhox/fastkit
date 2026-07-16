from datetime import datetime

import pytest

from fastkit_tasks.cron import CronError, next_run, parse_cron
from fastkit_tasks.registry import PermanentTaskError, TaskRegistry
from fastkit_tasks.retry import RetryPolicy, compute_delay


def test_registry_register_and_get():
    registry = TaskRegistry()

    @registry.task("emails.send", queue="email", max_attempts=5, timeout=30)
    async def handler(context, payload):
        return payload

    definition = registry.get("emails.send")
    assert definition.queue == "email"
    assert definition.max_attempts == 5
    assert registry.contains("emails.send")
    assert registry.names() == ["emails.send"]


def test_registry_duplicate_and_missing():
    registry = TaskRegistry()
    registry.task("a")(lambda context, payload: None)

    with pytest.raises(ValueError, match="already registered"):
        registry.task("a")(lambda context, payload: None)

    with pytest.raises(KeyError, match="not registered"):
        registry.get("missing")


def test_permanent_task_error_is_exception():
    assert issubclass(PermanentTaskError, Exception)


def test_retry_delays():
    assert compute_delay(RetryPolicy.fixed, 5, 3) == 5
    assert compute_delay(RetryPolicy.linear, 5, 3) == 15
    assert compute_delay(RetryPolicy.exponential, 5, 3) == 20
    assert compute_delay(RetryPolicy.exponential_jitter, 5, 3, jitter_source=0.5) == 30


def test_parse_cron_fields():
    minutes, hours, days, months, weekdays = parse_cron("*/15 0 1 * 1,3")

    assert minutes == {0, 15, 30, 45}
    assert hours == {0}
    assert days == {1}
    assert months == set(range(1, 13))
    assert weekdays == {1, 3}


def test_parse_cron_supports_ranges_and_steps():
    minutes, hours, days, months, weekdays = parse_cron("0 9-17 1-3 */2 *")

    assert hours == {9, 10, 11, 12, 13, 14, 15, 16, 17}
    assert days == {1, 2, 3}
    assert months == {1, 3, 5, 7, 9, 11}


def test_parse_cron_errors():
    with pytest.raises(CronError, match="5 fields"):
        parse_cron("* * *")

    with pytest.raises(CronError, match="out of range"):
        parse_cron("99 * * * *")

    with pytest.raises(CronError, match="out of range"):
        parse_cron("5-2 * * * *")

    with pytest.raises(CronError, match="invalid cron value"):
        parse_cron("abc * * * *")

    with pytest.raises(CronError, match="invalid step"):
        parse_cron("*/0 * * * *")


def test_next_run_day_of_month_or_weekday_when_both_restricted():
    # `0 0 13 * 5` fires on the 13th OR any Friday (POSIX OR semantics); AND would skip both
    friday = next_run("0 0 13 * 5", datetime(2026, 7, 14, 12, 0))
    thirteenth = next_run("0 0 13 * 5", datetime(2026, 7, 12, 12, 0))

    assert friday == datetime(2026, 7, 17, 0, 0)
    assert thirteenth == datetime(2026, 7, 13, 0, 0)


def test_next_run_hourly():
    result = next_run("0 * * * *", datetime(2026, 7, 14, 12, 30))

    assert result == datetime(2026, 7, 14, 13, 0)


def test_next_run_weekday():
    # cron weekday 1 = Monday; 2026-07-14 is a Tuesday
    result = next_run("0 9 * * 1", datetime(2026, 7, 14, 12, 0))

    assert result.weekday() == 0
    assert result.hour == 9


def test_next_run_impossible_raises():
    # february never has 30 days, so no match exists within a year
    with pytest.raises(CronError, match="no matching time"):
        next_run("0 0 30 2 *", datetime(2026, 7, 14, 12, 0))


def test_scheduler_aware_helper():
    from datetime import timezone

    from fastkit_tasks.scheduler import _aware

    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert _aware(aware) is aware
    assert _aware(datetime(2026, 1, 1)).tzinfo is timezone.utc
