# Reports in the admin

**One report = one screen = one menu item** (path `{admin}/reports/{name}`). Never several reports on
one page.

## Rendering

The report screen and its table partial are server-rendered by the pages router (`report_context`).
`initReport` (client) only wires the filter panel and swaps the `?_fragment=table` HTML into `#report`
by jQuery AJAX on Apply/Clear.

## Wiring

The consumer wires `report_data(name, session, locale, params, check)` (an async provider from its
report service) into `build_admin_pages_router`. The report screen is **authorization-gated**:
`dispatch_screen` passes the per-user `check(permission)->bool` into `report_data`; the consumer raises
`AuthorizationError` when denied (the demo requires `reports.view`), and the branch renders `error.html`
403.

Add the menu item:

```python
site.add_menu(definition.title, group="reports",
              path=f"{settings.admin.path}/reports/{name}",
              permission="reports.view", icon="report-analytics")
```

## Filters have full parity with grid filters

Report filters **are** the same `fastkit_admin.filters.*` objects, rendered by the same filter panel and
enhanced by the same client fn — including `LookupFilter`/`SelectFilter` with `options` + `depends_on`
cascades. Select/lookup options come from `ReportDefinition.options`, served by
`/reports/{name}/options/{field}`.

## Exports

Apply re-points the export links. The demo ships reports exporting CSV, HTML and PDF (an `fpdf2`
renderer). CSV export neutralizes formula injection; HTML escapes.

See [reports package](../packages/reports.md) and [Add a report](../guides/add-report.md).
