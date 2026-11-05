from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from enums.report_chart_period import ReportChartPeriod
from enums.report_column_kind import ReportColumnKind
from helpers.dates import add_months
from helpers.i18n import translate
from helpers.money import money, number
from helpers.settings import settings
from helpers.text import alphabetical
from services.report_chart import ReportChart
from services.report_column import ReportColumn
from services.report_document import ReportDocument
from services.report_plot import SLICED, ReportPlot
from services.report_series import ReportSeries

# The kinds of column a point of time is read off, which are drawn in order with every period between the first and the last.
TIMED = (ReportColumnKind.DATE, ReportColumnKind.DATETIME)

# What a chart may add up, because summing a label or a date means nothing.
MEASURED = (ReportColumnKind.INTEGER, ReportColumnKind.MONEY)

# How a point of time is labelled, which is the shape a date takes everywhere else a report writes one.
LABELLED = {ReportChartPeriod.DAY: "%Y-%m-%d", ReportChartPeriod.MONTH: "%Y-%m"}


@dataclass(frozen=True)
class GroupedReportChart(ReportChart):
    """A chart of the rows grouped by one column, counting them or adding up another column, with one chart per currency where what it adds up is money."""

    # The column each point is named by.
    category: str = ""

    # The column added up at each point, and none counts the rows instead.
    value: str | None = None

    # How a point of time is grouped, which only a date or an instant reads.
    period: ReportChartPeriod = ReportChartPeriod.DAY

    def check(self, columns: tuple[ReportColumn, ...]):
        kinds = {column.key: column.kind for column in columns}

        if self.category not in kinds:
            raise TypeError(f"the chart {self.key} is grouped by {self.category!r}, which is not a column of the report")

        if self.value is not None and kinds.get(self.value) not in MEASURED:
            raise TypeError(f"the chart {self.key} adds up {self.value!r}, which is not a number or an amount among the columns of the report")

    def plots(self, document: ReportDocument) -> tuple[ReportPlot, ...]:
        category = document.column(self.category)
        measured = None if self.value is None else document.column(self.value)
        totals: dict[str | None, dict[object, Decimal]] = {}

        for row in document.rows:
            point = self.point(document, category, row)
            amount = 1 if measured is None else row[measured.key]

            # A row that names no point, or holds nothing to add, has no place on the chart, the way an unpaid purchase has no day it was paid on.
            if point is None or amount is None:
                continue

            currency = row[measured.currency] if measured is not None and measured.kind == ReportColumnKind.MONEY else None
            points = totals.setdefault(currency, {})
            points[point] = points.get(point, Decimal(0)) + Decimal(amount)

        drawn = (self.drawn(document, category, measured, currency, totals[currency]) for currency in sorted(totals, key=str))

        return tuple(plot for plot in drawn if plot is not None)

    def point(self, document: ReportDocument, category: ReportColumn, row: dict) -> object:
        value = row[category.key]

        if value is None:
            return None

        if category.kind == ReportColumnKind.DATETIME:
            value = document.local(value).date()

        if category.kind in TIMED and self.period == ReportChartPeriod.MONTH:
            return value.replace(day=1)

        if category.kind in TIMED:
            return value

        return document.shown(category, row)

    def drawn(self, document: ReportDocument, category: ReportColumn, measured: ReportColumn | None, currency: str | None, points: dict[object, Decimal]) -> ReportPlot | None:
        if category.kind in TIMED:
            ordered = [(day.strftime(LABELLED[self.period]), points.get(day, Decimal(0))) for day in self.calendar(min(points), max(points))]
        else:
            ordered = sorted(points.items(), key=lambda item: alphabetical(item[0]))

        if self.kind in SLICED:
            ordered = self.sliced(document, ordered)

        # A whole with no slice larger than zero is no chart at all.
        if not ordered:
            return None

        labels = tuple(label for label, _ in ordered)
        values = tuple(total for _, total in ordered)
        shown = tuple(number(total, document.locale) if currency is None else money(total, currency, document.locale) for total in values)
        series = ReportSeries(name=self.measure(document, measured, currency), values=tuple(float(total) for total in values), shown=shown)
        title = translate(self.title, document.locale)

        # An amount is drawn on an axis that says nothing of its currency, so the title says it, and every currency is a chart of its own because adding two of them on one axis reads as one sum.
        if currency is not None:
            return ReportPlot(key=f"{self.key}-{currency.lower()}", title=f"{title} · {currency.upper()}", kind=self.kind, labels=labels, series=(series,), currency=currency)

        return ReportPlot(key=self.key, title=title, kind=self.kind, labels=labels, series=(series,))

    def calendar(self, first: date, last: date) -> list[date]:
        """Every period from the first point to the last, because a day nothing happened on is a zero and not a gap the chart closes over."""
        days = []
        day = first

        while day <= last:
            days.append(day)
            day = add_months(day, 1) if self.period == ReportChartPeriod.MONTH else day + timedelta(days=1)

        return days

    def sliced(self, document: ReportDocument, ordered: list[tuple[str, Decimal]]) -> list[tuple[str, Decimal]]:
        """The slices of a whole, which are only what adds something to it, with what the palette has no colour for added up as one last slice."""
        ordered = [item for item in ordered if item[1] > 0]

        if len(ordered) <= settings.charts.slots:
            return ordered

        largest = sorted(ordered, key=lambda item: item[1], reverse=True)
        kept = {label for label, _ in largest[: settings.charts.slots - 1]}
        rest = sum((total for label, total in ordered if label not in kept), Decimal(0))

        return [item for item in ordered if item[0] in kept] + [(translate("report.chart-other", document.locale), rest)]

    def measure(self, document: ReportDocument, measured: ReportColumn | None, currency: str | None) -> str:
        if measured is None:
            return translate("report.chart-count", document.locale)

        if currency is None:
            return document.heading(measured)

        return currency.upper()
