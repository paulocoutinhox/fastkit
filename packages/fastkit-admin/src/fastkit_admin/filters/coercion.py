from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

_SKIP = object()


def _coerce_for_column(column, value):
    """Coerce a query-string value to the column's Python type; return _SKIP if it does not parse."""

    if isinstance(value, (dict, list, set, tuple)):
        return _SKIP

    if isinstance(value, (int, float, Decimal, date, time, datetime)):
        return value

    try:
        python_type = column.type.python_type
    except (NotImplementedError, AttributeError):
        return value

    if python_type is bool:
        return value in ("true", "1", 1, True)

    try:
        if python_type is int:
            return int(value)

        if python_type is float:
            return float(value)

        if python_type is Decimal:
            return Decimal(value)

        if python_type is datetime:
            return datetime.fromisoformat(value)

        if python_type is date:
            return date.fromisoformat(value)

        if python_type is time:
            return time.fromisoformat(value)
    except (TypeError, ValueError, InvalidOperation):
        return _SKIP

    return value
