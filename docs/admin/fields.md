# Admin fields

Fields (`fastkit_admin.fields`) declare how a value is parsed, validated and rendered in the form and
detail screens. They are locale-aware.

## The field types

| Field | Notes |
|---|---|
| `TextField`, `TextareaField`, `EmailField`, `URLField` | Basic text. |
| `MaskedField` | An input mask. |
| `PasswordField` | Write-only. |
| `NumberField`, `DecimalField` | Locale-aware numbers; reject `bool`/list/dict → 422. |
| `BooleanField` | Rendered as a green check / red ✕. |
| `DateField`, `TimeField`, `DateTimeField` | Locale-aware; reject non-string JSON → 422. |
| `SelectField`, `MultiSelectField` | Choice fields; membership test guarded against unhashable values. |
| `RelationField`, `LookupField` | FK selects / autocomplete — see [Dependent selects](dependent-selects.md). |
| `ColorField` | Color picker. |
| `JsonField` | JSONEditor (tree + text). |
| `RichTextField` | TinyMCE; **sanitizes by default** (`sanitizer=None` to opt out). |
| `ImageField`, `FileField` | Uploads — see [Uploads & file fields](uploads-files.md). |
| `PermissionMatrixField` | Role permission matrix. |
| `TranslationsField` | Per-language content editing. |

## Common options

- `required`, `readonly`, `default`, `max_length`, `decimal_places`, etc.
- `virtual=True` — not persisted; saves through its own endpoint (matrix, translations).
- `hide_label=True` — render without a label (use the fieldset title instead).
- `label=` — the field's label (kept in the case you declare).

## Fieldsets

```python
fieldsets = [
    Fieldset("Identity", ["name", "email"], description="Who this is"),
    Fieldset("Record", ["id", "created_at", "updated_at"]),   # dropped on create if all read-only
]
```

Each `Fieldset` renders as its own card. A `Fieldset` whose fields are all filtered out (e.g. read-only
metadata on the create form) is **not rendered**.

## Robust parsing (no 500s)

Field parsers that coerce (`NumberField`, `RelationField`/`LookupField` `int()`, `MultiSelectField`
list) raise a 422 `FieldError`, not a raw `ValueError`/`TypeError`. Date/time fields reject a non-string
JSON value with a 422 instead of an `AttributeError`. So ordinary bad input is always a clean 422.

## Custom field types

Subclass `Field` and implement parse/format/validate. Field **widgets** on the client are the one
deliberately closed set (field types are backend-declared) — extend cells/headers/row-actions via
`FastKitAdmin` instead. See [Custom field](../guides/custom-field.md).
