from fastkit_admin.filters.base import Filter
from fastkit_admin.filters.coercion import _SKIP, _coerce_for_column


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
