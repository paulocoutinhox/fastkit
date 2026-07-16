from datetime import datetime, timedelta

_FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))


class CronError(ValueError):
    pass


def _to_int(value: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise CronError(f"invalid cron value '{value}'") from error


def _parse_token(token: str, low: int, high: int) -> set[int]:
    base, slash, step_spec = token.partition("/")
    step = _to_int(step_spec) if slash else 1

    if step <= 0:
        raise CronError(f"invalid step '{step_spec}'")

    if base == "*":
        start, end = low, high
    elif "-" in base:
        start_spec, _, end_spec = base.partition("-")
        start, end = _to_int(start_spec), _to_int(end_spec)
    else:
        start = end = _to_int(base)

    if start < low or end > high or start > end:
        raise CronError(f"value out of range [{low}, {high}] in '{token}'")

    return set(range(start, end + 1, step))


def _parse_field(spec: str, low: int, high: int) -> set[int]:
    values: set[int] = set()

    for token in spec.split(","):
        values.update(_parse_token(token, low, high))

    return values


def parse_cron(expression: str) -> tuple[set[int], ...]:
    fields = expression.split()

    if len(fields) != 5:
        raise CronError("cron expression must have exactly 5 fields")

    return tuple(_parse_field(field, low, high) for field, (low, high) in zip(fields, _FIELD_RANGES))


def next_run(expression: str, after: datetime) -> datetime:
    """Return the next minute strictly after `after` that matches the cron expression."""

    minutes, hours, days, months, weekdays = parse_cron(expression)
    days_restricted = days != set(range(_FIELD_RANGES[2][0], _FIELD_RANGES[2][1] + 1))
    weekdays_restricted = weekdays != set(range(_FIELD_RANGES[4][0], _FIELD_RANGES[4][1] + 1))

    candidate = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)

    for _ in range(366 * 24 * 60):
        cron_weekday = (candidate.weekday() + 1) % 7
        day_match = candidate.day in days
        weekday_match = cron_weekday in weekdays

        if days_restricted and weekdays_restricted:
            day_or_weekday = day_match or weekday_match
        else:
            day_or_weekday = day_match and weekday_match

        if candidate.minute in minutes and candidate.hour in hours and candidate.month in months and day_or_weekday:
            return candidate

        candidate += timedelta(minutes=1)

    raise CronError("no matching time found within one year")
