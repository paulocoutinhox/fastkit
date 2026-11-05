from abc import ABC, abstractmethod
from dataclasses import dataclass

from enums.report_chart_kind import ReportChartKind
from services.report_column import ReportColumn
from services.report_document import ReportDocument
from services.report_plot import ReportPlot


@dataclass(frozen=True)
class ReportChart(ABC):
    """A chart a report draws above its rows, which a report subclasses to work out any numbers its rows do not hold as they are."""

    key: str

    # The catalogue key of its title.
    title: str
    kind: ReportChartKind

    def check(self, columns: tuple[ReportColumn, ...]):
        """Refuses, where the report is written, a chart that names something its columns do not answer."""

    @abstractmethod
    def plots(self, document: ReportDocument) -> tuple[ReportPlot, ...]:
        """The charts this one draws over what a run answered, which is none where nothing was answered."""
