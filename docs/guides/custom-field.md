# Add a custom field type

Subclass `Field` to add a server-side field type (parse/validate/format). Client field **widgets** are
a closed set, so a custom field reuses an existing widget (`type`) or renders via a `render_<column>`
/ detail hook.

```python
from fastkit_admin.fields import Field
from fastkit_core.errors.exceptions import FieldError

class SlugField(Field):
    field_type = "text"        # the client widget to reuse

    def parse(self, value, locale):
        text = (value or "").strip().lower().replace(" ", "-")
        if not text:
            raise FieldError(self.name, "validation.required")
        return text

    def format_value(self, value, locale):
        return value or ""
```

Use it like any field:

```python
form_fields = [SlugField("slug", required=True)]
```

## When the value needs custom display

For a value that renders as markup (a badge, a computed cell), use a `render_<column>(row, locale)`
method on the resource (see [Columns](../admin/columns.md)) rather than a new client widget.

## When you need a brand-new widget

The field-widget switch on the client is deliberately closed (field types are backend-declared). Extend
**cells / headers / row-actions / dashboard** via `FastKitAdmin` instead — see
[Extend the admin client](extend-admin-client.md).

Test the parse/validate/format directly (`pytest`), and add an e2e if the widget behaviour is visible.
