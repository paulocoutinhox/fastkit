import csv
import io
import json
from html import escape

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


class JsonRenderer:
    name = "json"

    def render(self, result: ReportResult) -> bytes:
        payload = {"title": result.definition.title, "rows": result.rows}

        return json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")


_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value) -> str:
    text = "" if value is None else str(value)

    return f"'{text}" if text[:1] in _CSV_FORMULA_TRIGGERS else text


class CsvRenderer:
    name = "csv"

    def render(self, result: ReportResult) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        keys = result.column_keys()

        writer.writerow(
            [_csv_safe(column.label) for column in result.definition.columns]
        )

        for row in result.rows:
            writer.writerow([_csv_safe(row.get(key, "")) for key in keys])

        return buffer.getvalue().encode("utf-8")


class HtmlRenderer:
    name = "html"

    def render(self, result: ReportResult) -> str:
        keys = result.column_keys()
        header = "".join(
            f"<th>{escape(column.label)}</th>" for column in result.definition.columns
        )
        body_rows = []

        for row in result.rows:
            cells = "".join(f"<td>{escape(str(row.get(key, '')))}</td>" for key in keys)
            body_rows.append(f"<tr>{cells}</tr>")

        return f"<h1>{escape(result.definition.title)}</h1><table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


class PdfRenderer:
    """Renders the HTML result to PDF through an injectable backend (e.g. WeasyPrint)."""

    name = "pdf"

    def __init__(self, backend):
        self._backend = backend
        self._html = HtmlRenderer()

    def render(self, result: ReportResult) -> bytes:
        html = self._html.render(result)

        return self._backend(html)


def default_renderers() -> dict:
    return {
        renderer.name: renderer
        for renderer in (
            ScreenRenderer(),
            JsonRenderer(),
            CsvRenderer(),
            HtmlRenderer(),
        )
    }
