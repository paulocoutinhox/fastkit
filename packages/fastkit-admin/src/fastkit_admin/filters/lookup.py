from fastkit_admin.filters.select import SelectFilter


class LookupFilter(SelectFilter):
    filter_type = "lookup"

    def __init__(
        self,
        field: str,
        options: str,
        depends_on: list[str] | None = None,
        label: str | None = None,
        min_chars: int = 0,
        initial_limit: int = 10,
        search_limit: int = 20,
    ):
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
