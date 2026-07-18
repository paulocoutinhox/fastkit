from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_

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


class Filter:
    """Base filter that only ever touches an explicitly registered model column."""

    filter_type = "text"

    def __init__(self, field: str, label: str | None = None):
        self.field = field
        self.label = label or field.replace("_", " ").title()

    def column(self, model):
        return getattr(model, self.field)

    def to_schema(self) -> dict:
        return {"field": self.field, "type": self.filter_type, "label": self.label}

    def apply(self, query, model, value):
        return query


class EqualityFilter(Filter):
    """Filters that match a single coerced value against their column."""

    def apply(self, query, model, value):
        if value in (None, ""):
            return query

        column = self.column(model)
        coerced = _coerce_for_column(column, value)

        if coerced is _SKIP:
            return query

        return query.where(column == coerced)


class TextFilter(Filter):
    filter_type = "text"

    def apply(self, query, model, value):
        if not value:
            return query

        return query.where(self.column(model).ilike(f"%{value}%"))


class ExactFilter(EqualityFilter):
    filter_type = "exact"


class BooleanFilter(Filter):
    filter_type = "boolean"

    def apply(self, query, model, value):
        if value in (None, ""):
            return query

        truthy = value in (True, "true", "1", 1)

        return query.where(self.column(model).is_(truthy))


class NumberFilter(EqualityFilter):
    filter_type = "number"


class ChoiceFilter(EqualityFilter):
    filter_type = "choice"

    def __init__(self, field: str, choices: list[tuple[str, str]], label: str | None = None):
        super().__init__(field, label)
        self.choices = choices

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["choices"] = [{"value": value, "label": label} for value, label in self.choices]

        return schema


class DateRangeFilter(Filter):
    filter_type = "date_range"

    def apply(self, query, model, value):
        if not isinstance(value, dict):
            return query

        column = self.column(model)
        start = _coerce_for_column(column, value["from"]) if value.get("from") else None
        end = _coerce_for_column(column, value["to"]) if value.get("to") else None
        conditions = []

        if start not in (None, _SKIP):
            conditions.append(column >= start)

        if end not in (None, _SKIP):
            conditions.append(column <= end)

        if not conditions:
            return query

        return query.where(and_(*conditions))


class DateFilter(EqualityFilter):
    filter_type = "date"


class TimeFilter(EqualityFilter):
    filter_type = "time"


class DateTimeFilter(EqualityFilter):
    filter_type = "datetime"


class EnumFilter(EqualityFilter):
    filter_type = "enum"

    def __init__(self, field: str, choices: list[tuple[str, str]], label: str | None = None):
        super().__init__(field, label)
        self.choices = choices

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["choices"] = [{"value": value, "label": label} for value, label in self.choices]

        return schema


class SelectFilter(EqualityFilter):
    filter_type = "select"

    def __init__(self, field: str, choices: list[tuple[str, str]] | None = None, options: str | None = None, depends_on: list[str] | None = None, label: str | None = None):
        super().__init__(field, label)
        self.choices = choices or []
        self.options = options
        self.depends_on = depends_on or []

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["choices"] = [{"value": value, "label": label} for value, label in self.choices]
        schema["options"] = self.options
        schema["depends_on"] = self.depends_on

        return schema


class LookupFilter(SelectFilter):
    filter_type = "lookup"

    def __init__(self, field: str, options: str, depends_on: list[str] | None = None, label: str | None = None, min_chars: int = 0, initial_limit: int = 10, search_limit: int = 20):
        super().__init__(field, options=options, depends_on=depends_on, label=label)
        self.min_chars = min_chars
        self.initial_limit = initial_limit
        self.search_limit = search_limit

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["min_chars"] = self.min_chars
        schema["initial_limit"] = self.initial_limit
        schema["search_limit"] = self.search_limit

        return schema


class MultiChoiceFilter(Filter):
    filter_type = "multichoice"

    def __init__(self, field: str, choices: list[tuple[str, str]], label: str | None = None):
        super().__init__(field, label)
        self.choices = choices

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["choices"] = [{"value": value, "label": label} for value, label in self.choices]

        return schema

    def apply(self, query, model, value):
        if not value:
            return query

        column = self.column(model)
        values = value if isinstance(value, list) else [value]
        coerced = [item for item in (_coerce_for_column(column, entry) for entry in values) if item is not _SKIP]

        if not coerced:
            return query

        return query.where(column.in_(coerced))
