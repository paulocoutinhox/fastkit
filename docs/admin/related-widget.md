# Related-object widget

A Django-style **+ / pencil / trash** widget beside a `RelationField` or `LookupField` that manages
the related record **in a modal, without leaving the form**.

```python
class ProductAdmin(AdminResource[Product]):
    form_fields = [
        RelationField("category_id", label="Category", related="categories"),
        RelationField("subcategory_id", label="Subcategory", related="subcategories",
                      depends_on=["category_id"]),
    ]
```

`related="<resource name>"` renders the icons (`_related_buttons.html`) beside the control.

## How it works

The icons open the **related** resource's own form in a `FastKit.modal`, fetched from a
`?_fragment=form` render (`partials/_form.html` — the `<form>` alone, no shell), so the modal reuses
the entire server-rendered form pipeline (fields, inlines, validation). `openRelatedModal` runs
`enhance()` + `initInlines` and submits through the same `collect()` + `/api` (POST create / PATCH
edit), with errors shown **inside** the modal via `FastKit.formErrors`.

## What each icon does to the parent control

- **add** — reloads options + selects the new id (and resets its dependents, since the value changed).
- **delete** — clears the control, reloads its options so the deleted record drops out of the dropdown
  (not merely deselected), and resets dependents.
- **edit** — keeps the value and runs `refreshRelatedChain`: a general walk of the `depends_on` graph
  that reloads the edited field and **every field that (transitively) depends on it**, each keeping its
  current value if it still exists. The walk carries a visited set (no fan-out/cycle loops) and fires
  `change` when a value is invalidated so the reset-cascade clears the subtree below it.

## Permission-gated

`form_screen` attaches `related_flags` (`add`/`edit`/`delete` = the related resource's
`can_create`/`update`/`delete` for the acting user), so an icon renders only when allowed. Edit/delete
are server-rendered disabled until a value is selected. It works **nested** (a modal form's own related
fields open further modals).

See [Dependent selects & lookups](dependent-selects.md) and [Inlines](inlines.md).
