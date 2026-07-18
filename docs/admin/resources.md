# Admin resources

An `AdminResource[Model]` declares a CRUD grid, form, filters and actions over a model. You subclass
it and register the instance on the `admin_site`.

```python
from fastkit_admin.resource import AdminResource, Fieldset
from fastkit_admin.columns import Column
from fastkit_admin.fields import TextField, DecimalField, BooleanField
from fastkit_admin.filters import BooleanFilter

class ProductAdmin(AdminResource[Product]):
    name = "products"                 # kebab-case; drives the URL /admin/products
    label = "Products"                # sentence-cased page/menu title
    icon = "package"

    list_columns = ["name", DecimalField and Column("price", type="decimal"), "is_active",
                    Column("created_at", type="datetime")]
    clickable_columns = ["name"]      # None (default) = every cell links to the record
    search_fields = ["name", "sku"]
    filters = [BooleanFilter("is_active")]
    ordering = ["-created_at"]         # default: -pk_field (newest first)

    form_fields = [TextField("name", required=True), DecimalField("price", decimal_places=2),
                   BooleanField("is_active", label="Active")]
    fieldsets = [Fieldset("Details", ["name", "price", "is_active"])]

    permissions = {"list": "products.view", "create": "products.create",
                   "update": "products.update", "delete": "products.delete", "detail": "products.view"}
```

## Register it

```python
def register_admin(self, context):
    site = context.component("admin_site")
    instance = ProductAdmin()
    instance.assets = context.component("file_service")   # for file_fields (see uploads)
    instance.media_base_url = context.settings.storage.base_url
    site.register(instance)
    site.add_group("catalog", "Catalog", order=0, icon="package")
    site.add_menu("Products", group="catalog", resource="products")
```

## Key attributes

| Attribute | Meaning |
|---|---|
| `list_columns` | Grid columns — names or `Column(...)` / field objects. |
| `clickable_columns` | `None` = every cell links to the record; `[...]` = only those; `[]` = none. |
| `search_fields` | Enables the toolbar search. |
| `filters` | See [Filters](filters.md). |
| `actions` | Row / bulk / collection actions — see [Actions](actions.md). |
| `ordering` | Default sort; empty → `-pk_field`. |
| `form_fields` / `fieldsets` | The form — see [Fields](fields.md). |
| `inlines` | Repeatable child sub-forms — see [Inlines](inlines.md). |
| `pk_field` | The PK column used in payloads/checkbox/lookups (default `"id"`). |
| `read_only` | View-only resource; create/update/delete raise. |
| `file_fields` | Columns holding stored-file URLs — see [Uploads](uploads-files.md). |
| `select_all` | Bulk selection. |

## Overrides

`get_queryset`, `render_<column>`, `sort_<column>`, `resolve`, `display`, `display_label` — see
[Overrides](overrides.md).

## The admin never 500s on ordinary bad input

Field parsers coerce and raise 422 `FieldError`s (not raw `ValueError`/`TypeError`); grid filters skip
a value that doesn't parse; malformed inline payloads are ignored rather than wiping children. See
[Overrides](overrides.md) and [Filters](filters.md).
