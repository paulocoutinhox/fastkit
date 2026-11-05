from helpers.i18n import translate
from services.excel_book import ExcelBook
from services.excel_report_exporter import ExcelReportExporter
from services.report_document import ReportDocument


class SubscriptionsExcelExporter(ExcelReportExporter):
    """The subscriptions as a spreadsheet that opens on a sheet of the figures the screen draws above its charts."""

    def write(self, book: ExcelBook, document: ReportDocument):
        sheet = book.sheet(translate("report.summary", document.locale))

        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 16)

        for line, figure in enumerate(document.details["figures"]):
            sheet.write_string(line, 0, figure["label"], book.heading)
            sheet.write_number(line, 1, figure["value"])

        super().write(book, document)
