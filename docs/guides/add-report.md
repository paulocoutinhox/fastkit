# Add a report and exporters

## 1. Define the report

```python
from fastkit_reports import ReportDefinition
from fastkit_admin.filters import LookupFilter, NumberFilter

async def run(session, params, locale):
    rows = await query_prices(session, params)
    return rows

definition = ReportDefinition(
    name="product-prices",              # kebab-case
    title="Product prices",
    columns=[{"name": "name", "label": "Product"}, {"name": "price", "type": "decimal"}],
    filters=[
        LookupFilter("category_id", options="category_options"),
        LookupFilter("subcategory_id", options="subcategory_options", depends_on=["category_id"]),
        NumberFilter("max_price"),
    ],
    options={"category_options": category_options, "subcategory_options": subcategory_options},
    query=run,
)
```

The `filters` are the very same `fastkit_admin.filters.*` objects your grids use — full parity,
including cascading lookups.

## 2. Register it + the menu

```python
report_registry = context.component("report_registry")
report_registry.register(definition)
site.add_menu(definition.title, group="reports",
              path=f"{settings.admin.path}/reports/product-prices",
              permission="reports.view", icon="report-analytics")
```

## 3. Wire the screen and authorization

Pass `report_data(name, session, locale, params, check)` into `build_admin_pages_router`, raising
`AuthorizationError` when `check("reports.view")` is false.

## 4. Exporters

`ReportService.export_formats()` lists the non-screen renderers. Register a custom renderer (the demo
adds an `fpdf2` PDF renderer) and your report exports CSV, HTML and PDF automatically. CSV output is
formula-injection-safe; HTML is escaped.

See [Reports in the admin](../admin/reports-in-admin.md) and the [reports package](../packages/reports.md).
