from dataclasses import dataclass

from enums.report_chart_kind import ReportChartKind
from helpers.settings import settings
from services.report_series import ReportSeries

# The kinds where each label is a slice of one whole, and a slice past the palette would wear the colour of another.
SLICED = (ReportChartKind.PIE, ReportChartKind.DOUGHNUT)


@dataclass(frozen=True)
class ReportPlot:
    """A chart with its numbers already worked out, which the screen, the printed page and the spreadsheet each draw the same way."""

    key: str
    title: str
    kind: ReportChartKind
    labels: tuple[str, ...]
    series: tuple[ReportSeries, ...]

    # The currency every amount of the chart is in, and none where it draws counts or plain numbers.
    currency: str | None = None

    def __post_init__(self):
        if not self.labels:
            raise ValueError(f"the chart {self.key} draws at least one point")

        if any(len(series.values) != len(self.labels) for series in self.series):
            raise ValueError(f"every series of the chart {self.key} has a value for each of its labels")

        # A series past the palette would take a colour another one already wears, and two series read as one.
        if len(self.series) > settings.charts.slots:
            raise ValueError(f"the chart {self.key} draws more series than the palette has colours")

        # A slice is a part of a whole, and nothing or less than nothing is not a part of anything.
        if self.kind in SLICED and any(value <= 0 for series in self.series for value in series.values):
            raise ValueError(f"every slice of the chart {self.key} is larger than zero")
