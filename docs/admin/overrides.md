# Admin resource overrides

Django-style method overrides on `AdminResource` let you shape queries, cells, sorting and labels.

## `get_queryset()`

Return the base SQLAlchemy `select` — filter, join, restrict columns:

```python
def get_queryset(self):
    return select(self.model).where(self.model.is_active.is_(True))
```

## `render_<column>(row, locale)`

Return a cell's HTML (marks the column `html`, rendered as markup). Also drives the detail screen via
`serialize_detail`'s `_html` map, so a badge/custom cell renders the same on the view screen. See
[Columns](columns.md).

## `sort_<column>()`

Return the SQLAlchemy expression a column sorts by. See [Columns](columns.md).

## `resolve(session, rows, locale)`

An async hook called with the page's rows **before serialization** — bulk-load related entities and
stash labels on each row so sync `render_<column>` methods stay N+1-free:

```python
async def resolve(self, session, rows, locale):
    user_ids = {r.user_id for r in rows}
    users = await load_users(session, user_ids)
    for r in rows:
        r._user_label = users[r.user_id].display_label()
```

## `display(row)` / `display_label`

`AdminResource.display(row)` returns the text shown for a record. It calls the model's
`display_label()` when present, else the pk. It drives the detail/view screen title and any column that
references another entity. Override `display()` for full control.

## `pk_field`

Default `"id"`. Set it for models with a non-`id` primary key — it is the record id in payloads, the
row checkbox and lookups.

## `read_only = True`

Makes the resource view-only: `permission_flags` reports `can_create/update/delete = False`, and
create/update/delete raise. Bulk delete and single delete both go through `delete()` per record, so
file cleanup and DB cascades always run — there is no raw delete query.

## Save hooks

`before_create`/`after_create`, `before_update`/`after_update`, `before_delete` let you adjust parsed
data or run side effects within the same transaction.
