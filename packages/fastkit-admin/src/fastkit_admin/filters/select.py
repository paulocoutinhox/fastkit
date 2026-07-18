from fastkit_admin.filters.equality import EqualityFilter


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
