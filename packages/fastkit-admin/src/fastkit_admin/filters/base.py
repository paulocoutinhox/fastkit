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
