from html import escape

from fastkit_reports.contracts import ReportResult


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
