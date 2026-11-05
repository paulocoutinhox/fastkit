from dataclasses import dataclass


@dataclass(frozen=True)
class ReportSeries:
    """One run of values of a chart, with each value also written the way its reader reads it."""

    name: str
    values: tuple[float, ...]
    shown: tuple[str, ...]
