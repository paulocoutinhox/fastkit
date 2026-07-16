# fastkit-reports

Report definitions and renderers for FastKit. Screen and PDF share the same
result.

## Installation

```bash
pip install fastkit-reports
pip install "fastkit-reports[pdf]"
```

## Definitions

```python
ReportDefinition(
    name="sales",
    title="Sales Report",
    columns=[ReportColumn("product", "Product"), ReportColumn("total", "Total", align="right")],
    query=sales_query,   # async (session, params) -> list[dict]
    filters=[ReportFilter("minimum", "Minimum total", "number")],
)
```

## Renderers

`ScreenRenderer` (structured dict), `JsonRenderer`, `CsvRenderer`, `HtmlRenderer`
(escaped) and `PdfRenderer` (HTML through an injectable backend such as
WeasyPrint). Register extra renderers with `ReportService.add_renderer`.

## Execution

```python
result = await report_service.render("sales", session, "csv", params={"minimum": 100})
execution = await report_service.execute("sales", "pdf", params={...})
```

`ReportExecution` tracks status, progress, row count and errors for heavy runs.

## Testing

100% branch coverage, including HTML escaping, PDF backend and execution
success/failure.

```bash
pytest packages/fastkit-reports --cov=fastkit_reports --cov-branch
```
