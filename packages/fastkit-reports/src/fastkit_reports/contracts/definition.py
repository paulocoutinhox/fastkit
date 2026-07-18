from dataclasses import dataclass, field
from typing import Awaitable, Callable

from fastkit_reports.contracts.column import ReportColumn


@dataclass
class ReportDefinition:
    name: str
    title: str
    columns: list[ReportColumn]
    query: Callable[..., Awaitable[list[dict]]]
    filters: list = field(default_factory=list)
    options: dict = field(default_factory=dict)

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "columns": [
                {"key": column.key, "label": column.label, "align": column.align}
                for column in self.columns
            ],
            "filters": [item.to_schema() for item in self.filters],
        }
