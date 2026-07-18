from fastkit_admin.filters.base import Filter
from fastkit_admin.filters.coercion import _SKIP, _coerce_for_column


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
