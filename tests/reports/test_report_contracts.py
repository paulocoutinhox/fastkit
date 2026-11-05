import zipfile
from datetime import date, datetime
from io import BytesIO

import pytest
from weasyprint.urls import FatalURLFetchingError

from enums.report_column_kind import ReportColumnKind
from helpers import templates
from services.csv_report_exporter import CsvReportExporter
from services.excel_report_exporter import ExcelReportExporter
from services.pdf_report_exporter import PdfReportExporter
from services.report import Report
from services.report_column import ReportColumn
from services.report_document import ReportDocument
from services.report_exporter import ReportExporter

COLUMNS = (ReportColumn("name", "report.column-email"), ReportColumn("day", "report.column-started-at", ReportColumnKind.DATE), ReportColumn("count", "report.column-plan", ReportColumnKind.INTEGER))


def written(rows: list[dict]) -> ReportDocument:
    return ReportDocument(title="Accounts", brand_name="Acme", brand_code="", generated_at=datetime(2026, 1, 2, 3, 4), columns=COLUMNS, rows=rows, locale="en", zone="UTC")


def test_a_report_missing_what_it_answers_with_fails_where_it_is_written():
    with pytest.raises(TypeError):

        class Unfinished(Report):
            code = "unfinished"
            title = "report.purchases"


def test_a_format_missing_what_it_is_named_by_fails_where_it_is_written():
    with pytest.raises(TypeError):

        class Nameless(ReportExporter):
            def render(self, document):
                return b""


def test_a_format_that_renders_nothing_is_never_built():
    class Silent(ReportExporter):
        code = "silent"
        label = "report.format-csv"
        media_type = "text/plain"
        extension = "txt"

    with pytest.raises(TypeError):
        Silent()


def test_a_column_that_cannot_be_read_fails_where_it_is_written():
    with pytest.raises(ValueError):
        ReportColumn("status", "report.column-status", ReportColumnKind.ENUM)

    with pytest.raises(ValueError):
        ReportColumn("price", "report.column-price", ReportColumnKind.MONEY)


def test_a_comma_separated_file_never_hands_a_spreadsheet_a_formula():
    file = CsvReportExporter().render(written([{"name": "=HYPERLINK(1)", "day": date(2026, 1, 2), "count": -3}, {"name": None, "day": None, "count": None}]))

    assert file.decode("utf-8-sig").splitlines() == ["Email,Started at,Plan", "'=HYPERLINK(1),2026-01-02,-3", ",,"]


def test_a_spreadsheet_writes_typed_text_as_text_and_never_as_a_formula():
    book = zipfile.ZipFile(BytesIO(ExcelReportExporter().render(written([{"name": "=1+1", "day": date(2026, 1, 2), "count": 7}, {"name": None, "day": None, "count": None}]))))
    sheet = book.read("xl/worksheets/sheet1.xml").decode()

    assert "<f>" not in sheet
    assert "=1+1" in book.read("xl/sharedStrings.xml").decode()
    assert "<v>7</v>" in sheet


def test_a_printed_report_reaches_nothing_outside_the_page(monkeypatch):
    monkeypatch.setattr(templates, "render", lambda *arguments: '<img src="file:///etc/passwd">')

    with pytest.raises(FatalURLFetchingError):
        PdfReportExporter().render(written([]))


def test_a_printed_report_with_no_row_says_so():
    assert PdfReportExporter().render(written([])).startswith(b"%PDF-")
