# Admin columns

Columns (`fastkit_admin.columns`) declare the grid cells.

```python
from fastkit_admin.columns import Column

list_columns = ["name", Column("price", align="end", type="decimal"),
                Column("created_at", type="datetime"), "is_active"]
```

`Column(name, align, sortable, type)`. A bare string is a column with defaults.

## Type-driven, locale-aware formatting

`type` (else the mapped field's `field_type`, else `"text"`) drives client-side, locale-aware
formatting:

- `date` / `datetime` / `time` and `number` / `decimal` are sent raw and formatted in the **user's
  timezone/locale** in the browser.
- `boolean` renders a green check / red ✕ icon (header and cells **center-aligned by default**).
- `null`/empty renders a Django-style dash `—`.

## Custom cell rendering

A `render_<column>(row, locale)` method returns a cell's HTML and marks that column `html` in the
schema (rendered as markup, never escaped):

```python
def render_status(self, row, locale):
    return '<span class="badge bg-green">Active</span>' if row.is_active else '<span class="badge">Off</span>'
```

A `render_<column>` always wins over type formatting. Exclude a column whose render returns its own
`<a>`/interactive markup from `clickable_columns` to avoid a nested link.

## Sorting

Sorting is applied per column. Override how a column sorts with `sort_<column>()` returning a
SQLAlchemy expression:

```python
def sort_full_name(self):
    return func.concat(self.model.first_name, " ", self.model.last_name)
```

## Click-through

`clickable_columns` is resource-level: `None` (default) makes **every** cell link to the record (edit
when `can_update`, else the detail view, else not a link). Links are visually neutral
(`.fk-cell-link`: inherits color/weight, no underline) so a linked cell reads as plain text.
