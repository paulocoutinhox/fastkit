from dataclasses import dataclass

from enums.report_column_kind import ReportColumnKind


@dataclass(frozen=True)
class ReportColumn:
    """One column of a report: the key a row answers it under, the catalogue key of its heading, and the kind of value it holds."""

    key: str
    label: str
    kind: ReportColumnKind = ReportColumnKind.TEXT

    # The catalogue an enum value is read through, as the API publishes it in `/api/meta`.
    enum_name: str | None = None

    # The key of the row that names the currency of an amount, because an amount read without its currency is a number nobody can read.
    currency: str | None = None

    def __post_init__(self):
        if self.kind == ReportColumnKind.ENUM and self.enum_name is None:
            raise ValueError(f"the enum column {self.key} names the catalogue its values are read through")

        if self.kind == ReportColumnKind.MONEY and self.currency is None:
            raise ValueError(f"the money column {self.key} names the column its currency is read from")
