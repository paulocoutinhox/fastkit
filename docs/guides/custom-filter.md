# Add a custom filter

Subclass `Filter`, implement `apply` (mutate the query) and `to_schema` (describe the widget).

```python
from fastkit_admin.filters import Filter

class PriceBandFilter(Filter):
    def __init__(self, field, choices):
        super().__init__(field)
        self.choices = choices   # [("cheap", "< 10"), ("mid", "10–100"), ("premium", "> 100")]

    def apply(self, query, model, value):
        column = getattr(model, self.field)
        if value == "cheap":
            return query.where(column < 10)
        if value == "premium":
            return query.where(column > 100)
        if value == "mid":
            return query.where(column.between(10, 100))
        return query   # unknown value → skip the filter, never raise

    def to_schema(self):
        return {"field": self.field, "type": "choice",
                "choices": [{"value": v, "label": l} for v, l in self.choices]}
```

Use it:

```python
filters = [PriceBandFilter("price", [("cheap", "< 10"), ("mid", "10–100"), ("premium", "> 100")])]
```

## Rules

- **Never 500 on bad input.** Coerce and, if the value doesn't fit, return the query unchanged. The
  built-in filters skip a value that doesn't parse to the column type.
- Reuse a client widget `type` (`text`/`number`/`boolean`/`choice`/`date`/`daterange`/`select`/`lookup`)
  in `to_schema`.
- The same filter object works in a [report](../admin/reports-in-admin.md) unchanged.

See [Filters](../admin/filters.md).
