import csv
import io

from fastkit_reports.contracts import ReportResult

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
