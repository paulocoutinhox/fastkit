# Dependent selects and lookups

Relation selects and autocomplete lookups can **cascade**: a child's options depend on the parent's
value, to any depth.

## Options handlers

Options come from an `options_<field>(session, params, locale)` handler on the resource — you decide
the query and the label:

```python
class GeoAdmin(AdminResource[...]):
    form_fields = [
        RelationField("country_id"),
        RelationField("state_id", depends_on=["country_id"]),
        LookupField("city_id", depends_on=["state_id"], min_chars=0),
    ]

    async def options_state_id(self, session, params, locale):
        country = params.get("country_id")
        return [] if not country else [{"value": s.id, "label": s.name} for s in states_of(country)]
```

Served by `GET /resources/{r}/options/{field}`. `params` contains parent field values (for
`depends_on`), plus `q` (lookup search), `value` (lookup preload) and `limit`.

## LookupField

`LookupField(min_chars=0, initial_limit=10, search_limit=20)` opens the dropdown **on focus** with
`initial_limit` results (no typing needed), then sends `search_limit` while the user searches — the
handler honours `params["limit"]`.

## Consistency guarantees (the client)

- **A lookup's committed value only survives while its text matches the picked label.** Editing or
  emptying the input immediately clears the value and fires `change`, so deleting a parent lookup's text
  (not only picking a new option) cascades the reset down the whole chain — a child can never keep
  searching with a stale parent id.
- **Resets cascade recursively to any depth** — changing a select/lookup resets its direct children and
  re-fires `change` on each, so a 4-level `country → state → city → district` chain fully clears/reloads
  every level below the one that changed.
- **Value-first on edit** — independent selects load, then each loads its own dependents once its value
  is set, so an edit form fills every level. Submit is blocked while dependent options are still loading
  (a record is never saved with cleared fields).
- **Loading feedback** — a fetching select is disabled with a corner spinner; a fetching lookup shows a
  translated loading message; menus close on an outside click, and a late response only re-opens a menu
  if the input is still focused.

## Filters too

The same cascade applies to `SelectFilter`/`LookupFilter` in the filter panel and in
[reports](reports-in-admin.md). The demo's **Geo samples** resource exercises a real 4-level chain as
selects and lookups, in the form and the filter panel.
