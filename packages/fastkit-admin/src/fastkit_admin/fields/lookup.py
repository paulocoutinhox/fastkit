from fastkit_admin.fields.relation import RelationField


class LookupField(RelationField):
    """Autocomplete relation: options are searched live as the user types.

    Options come from the same `options_<name>` handler, which receives the typed
    query under `q` and can decide both what to search and what label to show. It
    supports `depends_on` for cross-select filtering and preloads the current value.
    """

    field_type = "lookup"

    def __init__(
        self,
        *args,
        min_chars: int = 0,
        initial_limit: int = 10,
        search_limit: int = 20,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.min_chars = min_chars
        self.initial_limit = initial_limit
        self.search_limit = search_limit

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["min_chars"] = self.min_chars
        schema["initial_limit"] = self.initial_limit
        schema["search_limit"] = self.search_limit

        return schema
