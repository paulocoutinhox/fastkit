class InlineResource:
    """A repeatable child sub-form rendered inside a parent resource's form.

    The parent form serializes each inline's rows into a nested payload
    (`{<inline_name>: [{...}, ...]}`) and submits it to the resource write endpoint,
    where the consumer owns the transaction for interdependent data.
    """

    def __init__(self, name: str, form_fields: list, label: str | None = None, min_items: int = 0, max_items: int | None = None):
        self.name = name
        self.form_fields = form_fields
        self.label = label or name.replace("_", " ").title()
        self.min_items = min_items
        self.max_items = max_items

    def schema(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "fields": [field.to_schema() for field in self.form_fields],
            "min_items": self.min_items,
            "max_items": self.max_items,
        }
