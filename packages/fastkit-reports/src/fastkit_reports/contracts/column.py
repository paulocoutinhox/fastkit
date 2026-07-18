from dataclasses import dataclass


@dataclass(frozen=True)
class ReportColumn:
    key: str
    label: str
    align: str = "left"
