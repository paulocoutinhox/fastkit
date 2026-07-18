# Admin filters

Filters (`fastkit_admin.filters`) power the grid's Filters panel and are reused verbatim by
[reports](reports-in-admin.md).

## The filter types

`TextFilter`, `ExactFilter`, `BooleanFilter`, `NumberFilter`, `ChoiceFilter`, `EnumFilter`,
`DateFilter` / `TimeFilter` / `DateTimeFilter` / `DateRangeFilter`, `MultiChoiceFilter`, plus:

- **`SelectFilter(field, choices | options, depends_on)`** — an options-backed select.
- **`LookupFilter(field, options, depends_on, min_chars, initial_limit, search_limit)`** — an
  autocomplete lookup.

`SelectFilter`/`LookupFilter` reuse the resource's `options_<field>` handler, so selects and lookups
work as filters with `depends_on` cascades of any depth.

```python
filters = [
    BooleanFilter("is_active"),
    LookupFilter("category_id", options="category_options"),
    LookupFilter("subcategory_id", options="subcategory_options", depends_on=["category_id"]),
    Fieldset("Advanced", ["price"]),   # group filters into a titled card
]
```

A `filters` list may contain `Fieldset(title, [fields])` entries; the client renders the panel grouped,
with Apply / Clear.

## Applying

Apply sends `filter[field]` (and `filter[field][from]`/`[to]` for ranges) to the list endpoint;
`parse_grid_query` expects exactly that shape.

## Never 500 on bad filter input

- Values are coerced to the column's Python type via `filters._coerce_for_column`; a value that
  doesn't parse **skips the filter** — `filter[price]=abc` can't raise a Postgres `DataError`.
- `DateRangeFilter.apply` returns the query unchanged when the value is not a `{from,to}` dict.
- A non-scalar value (dict/list) is skipped rather than raising.

## Custom filters

Subclass `Filter` and implement `apply(query, model, value)` + `to_schema()`. See
[Custom filter](../guides/custom-filter.md).
