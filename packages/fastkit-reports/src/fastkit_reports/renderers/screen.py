from fastkit_reports.contracts import ReportResult


class ScreenRenderer:
    """Structured result for on-screen rendering, sharing the same data as the PDF."""

    name = "screen"

    def render(self, result: ReportResult) -> dict:
        return {
            "title": result.definition.title,
            "columns": [
                {"key": column.key, "label": column.label, "align": column.align}
                for column in result.definition.columns
            ],
            "rows": result.rows,
        }
