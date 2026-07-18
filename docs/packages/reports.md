# fastkit-reports

Read-only reports with filters and multiple export formats. **One report = one screen = one menu
item.**

## Define a report

```python
ReportDefinition(
    name="product-prices",
    title="Product prices",
    columns=[...],
    filters=[...],          # the same fastkit_admin.filters.* objects as CRUD grids
    options={...},          # {field: async handler(session, params, locale)} for select/lookup filters
    query=async_handler,    # returns the rows
)
```

`fastkit-reports` never imports `fastkit-admin` — `ReportDefinition.filters` is a plain `list` of
`to_schema()`-able (duck-typed) objects, so a consumer that has both packages passes admin filters
straight in. **Report filters have full parity with CRUD grid filters** — including
`LookupFilter`/`SelectFilter` with `options` + `depends_on` cascades.

## Exporters

`ReportService.export_formats()` lists the non-screen renderers. The framework escapes HTML and
**neutralizes CSV formula injection** (`_csv_safe` prefixes a cell starting with `= + - @`/tab/CR with
`'`). The demo adds an `fpdf2` PDF renderer and ships reports exporting CSV, HTML and PDF.

## Endpoints

`/api/reports`, `/api/reports/{name}/run`, `/api/reports/{name}/options/{field}`,
`/api/reports/{name}/export.{fmt}` (all accept the filter params as query string).

In the admin, see [Reports in the admin](../admin/reports-in-admin.md) and
[Add a report](../guides/add-report.md).
