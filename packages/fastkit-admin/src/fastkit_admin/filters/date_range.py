from sqlalchemy import and_

from fastkit_admin.filters.base import Filter
from fastkit_admin.filters.coercion import _SKIP, _coerce_for_column


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
