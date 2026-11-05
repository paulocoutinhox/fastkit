import csv
from io import StringIO

from enums.report_column_kind import ReportColumnKind
from services.report_document import ReportDocument
from services.report_exporter import ReportExporter

# What a spreadsheet opening the file would read as the start of a formula, which a value written by somebody else must never become.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")

# Text a person typed, as opposed to a number or a date this side wrote.
TYPED = (ReportColumnKind.TEXT, ReportColumnKind.ENUM)


class CsvReportExporter(ReportExporter):
    """A report as comma separated text, which a report offers when what reads it is another program rather than a person."""

    code = "csv"
    label = "report.format-csv"
    media_type = "text/csv"
    extension = "csv"

    def render(self, document: ReportDocument) -> bytes:
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow([document.heading(column) for column in document.columns])

        for row in document.rows:
            writer.writerow([self.cell(column.kind, document.shown(column, row)) for column in document.columns])

        # The mark in front is what makes a spreadsheet read the file as UTF-8 instead of guessing a code page and mangling every accent.
        return ("\ufeff" + output.getvalue()).encode("utf-8")

    def cell(self, kind: ReportColumnKind, shown: str | None) -> str:
        if shown is None:
            return ""

        # A value a person typed that opens like a formula is quoted, which is what keeps opening the file from running it.
        if kind in TYPED and shown.startswith(FORMULA_START):
            return f"'{shown}"

        return shown
