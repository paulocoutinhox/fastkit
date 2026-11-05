from datetime import datetime
from io import BytesIO

import xlsxwriter

from enums.report_chart_kind import ReportChartKind
from enums.report_column_kind import ReportColumnKind
from helpers.i18n import translate
from helpers.settings import settings
from services.excel_book import ExcelBook
from services.report_document import ReportDocument
from services.report_exporter import ReportExporter
from services.report_plot import SLICED, ReportPlot

# A column is as wide as what it holds, up to a width where reading it is easier wrapped.
WIDTH_MAX = 60

# The chart each kind is drawn as, which is a chart of the spreadsheet itself and keeps reading the cells beside it.
CHART_TYPES = {ReportChartKind.COLUMN: "column", ReportChartKind.BAR: "bar", ReportChartKind.LINE: "line", ReportChartKind.AREA: "area", ReportChartKind.PIE: "pie", ReportChartKind.DOUGHNUT: "doughnut"}

# How large a chart is drawn, and how many rows of the sheet it covers, so the next one starts below it.
CHART_SIZE = {"width": 640, "height": 320}

CHART_ROWS = 18

# The cells a chart reads sit to its left, and the chart starts after them and a column of air.
CHART_GAP = 1


class ExcelReportExporter(ReportExporter):
    """A report as a spreadsheet, where a number, an amount and a date are cells of their own kind and never text a formula cannot read, with the charts on a sheet before the rows."""

    code = "excel"
    label = "report.format-excel"
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    extension = "xlsx"

    def render(self, document: ReportDocument) -> bytes:
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        workbook.set_properties({"title": document.title, "company": document.brand_name, "created": document.generated_at.replace(tzinfo=None)})

        self.write(ExcelBook(workbook), document)
        workbook.close()

        return output.getvalue()

    def write(self, book: ExcelBook, document: ReportDocument):
        """The sheets of the file in the order the screen draws them, which a format of a report's own overrides to add, drop or reorder sheets."""
        if document.plots:
            self.write_charts(book, book.sheet(translate("report.charts", document.locale)), document)

        self.write_rows(book, book.sheet(document.title), document)

    def write_charts(self, book: ExcelBook, sheet, document: ReportDocument):
        line = 0

        sheet.set_column(0, 0, 24)

        for plot in document.plots:
            self.write_plot(book, sheet, line, plot)
            line += max(len(plot.labels) + 3, CHART_ROWS)

    def write_plot(self, book: ExcelBook, sheet, line: int, plot: ReportPlot):
        """The numbers of one chart as cells, and the chart of the spreadsheet drawn beside them reading those cells."""
        first = line + 2
        last = first + len(plot.labels) - 1
        cell = book.amount(plot.currency) if plot.currency is not None else None
        chart = book.workbook.add_chart({"type": CHART_TYPES[plot.kind]})

        sheet.write_string(line, 0, plot.title, book.title)

        for index, label in enumerate(plot.labels):
            sheet.write_string(first + index, 0, label)

        for column, series in enumerate(plot.series, start=1):
            sheet.write_string(line + 1, column, series.name, book.heading)

            for index, value in enumerate(series.values):
                sheet.write_number(first + index, column, value, cell)

            chart.add_series({"name": [sheet.name, line + 1, column], "categories": [sheet.name, first, 0, last, 0], "values": [sheet.name, first, column, last, column], **self.painted(plot, column - 1)})

        chart.set_title({"name": plot.title, "name_font": {"size": 11, "bold": True}})
        chart.set_size(CHART_SIZE)

        # One series is named by the title, and a slice is named by the legend because it is the one thing that tells the slices apart beside their colour.
        if len(plot.series) == 1 and plot.kind not in SLICED:
            chart.set_legend({"none": True})

        if plot.currency is not None and plot.kind not in SLICED:
            chart.set_y_axis({"num_format": book.amount_format(plot.currency)})

        sheet.insert_chart(line, len(plot.series) + 1 + CHART_GAP, chart)

    def painted(self, plot: ReportPlot, index: int) -> dict:
        """The colours of a series, which are the ones the screen and the printed page paint it with."""
        colours = settings.charts.light

        if plot.kind in SLICED:
            return {"points": [{"fill": {"color": colour}, "border": {"color": "#ffffff", "width": 1.5}} for colour in colours[: len(plot.labels)]]}

        if plot.kind == ReportChartKind.LINE:
            return {"line": {"color": colours[index], "width": 2}}

        return {"fill": {"color": colours[index]}, "border": {"none": True}}

    def write_rows(self, book: ExcelBook, sheet, document: ReportDocument):
        widths = [len(document.heading(column)) for column in document.columns]

        for index, column in enumerate(document.columns):
            sheet.write_string(0, index, document.heading(column), book.heading)

        for line, row in enumerate(document.rows, start=1):
            for index, column in enumerate(document.columns):
                value = row[column.key]
                shown = document.shown(column, row)
                widths[index] = max(widths[index], len(shown or ""))

                if value is None:
                    sheet.write_blank(line, index, None)

                    continue

                if column.kind == ReportColumnKind.INTEGER:
                    sheet.write_number(line, index, value)
                elif column.kind == ReportColumnKind.MONEY:
                    sheet.write_number(line, index, float(value), book.amount(row[column.currency]))
                elif column.kind == ReportColumnKind.DATE:
                    sheet.write_datetime(line, index, datetime(value.year, value.month, value.day), book.dated)
                elif column.kind == ReportColumnKind.DATETIME:
                    sheet.write_datetime(line, index, document.local(value), book.timed)
                else:
                    # Text and the label of an enum are words, written as a string so a value that begins with an equals sign is never read back as a formula.
                    sheet.write_string(line, index, shown)

        for index, width in enumerate(widths):
            sheet.set_column(index, index, min(width + 2, WIDTH_MAX))

        sheet.freeze_panes(1, 0)

        if document.columns:
            sheet.autofilter(0, 0, len(document.rows), len(document.columns) - 1)
