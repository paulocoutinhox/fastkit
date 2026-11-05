from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from enums.report_column_kind import ReportColumnKind
from helpers.dates import as_utc, read_in
from helpers.i18n import translate
from helpers.money import money, number
from services.report_column import ReportColumn
from services.report_plot import ReportPlot

# How a value of each kind is read on a page, in the language and on the clock of whoever asked for it.
SHOWN: dict[ReportColumnKind, Callable[["ReportDocument", ReportColumn, object, dict], str]] = {
    ReportColumnKind.TEXT: lambda document, column, value, row: str(value),
    ReportColumnKind.INTEGER: lambda document, column, value, row: number(value, document.locale),
    ReportColumnKind.MONEY: lambda document, column, value, row: money(value, row[column.currency], document.locale),
    ReportColumnKind.DATE: lambda document, column, value, row: value.isoformat(),
    ReportColumnKind.DATETIME: lambda document, column, value, row: read_in(value, document.zone, "%Y-%m-%d %H:%M"),
    ReportColumnKind.ENUM: lambda document, column, value, row: translate(f"enum.{column.enum_name}.{value}", document.locale),
}


@dataclass(frozen=True)
class ReportDocument:
    """What one run of a report answered, with everything an exporter needs to write it down: the words, the rows and the reader they are written for."""

    title: str
    brand_name: str
    brand_code: str
    generated_at: datetime
    columns: tuple[ReportColumn, ...]
    rows: list[dict]
    locale: str
    zone: str

    # The charts drawn above the rows, worked out once so every format draws the same numbers.
    plots: tuple[ReportPlot, ...] = ()

    # Whatever else a report answers for a screen, a template or a format of its own, as plain values a page can carry.
    details: dict = field(default_factory=dict)

    @property
    def generated(self) -> str:
        return read_in(self.generated_at, self.zone, "%Y-%m-%d %H:%M")

    def column(self, key: str) -> ReportColumn:
        return next(column for column in self.columns if column.key == key)

    def heading(self, column: ReportColumn) -> str:
        return translate(column.label, self.locale)

    def shown(self, column: ReportColumn, row: dict) -> str | None:
        """A value as somebody reading it expects it written, and nothing at all where the row holds none."""
        value = row[column.key]

        if value is None:
            return None

        return SHOWN[column.kind](self, column, value, row)

    def local(self, value: datetime) -> datetime:
        """An instant on the clock of the reader with no offset left, which is what a spreadsheet cell holds."""
        return as_utc(value).astimezone(ZoneInfo(self.zone)).replace(tzinfo=None)
