from fastkit_admin.filters.equality import EqualityFilter


class EnumFilter(EqualityFilter):
    filter_type = "enum"

    def __init__(
        self, field: str, choices: list[tuple[str, str]], label: str | None = None
    ):
        super().__init__(field, label)
        self.choices = choices

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["choices"] = [
            {"value": value, "label": label} for value, label in self.choices
        ]

        return schema
