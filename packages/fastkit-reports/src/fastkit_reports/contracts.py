from dataclasses import dataclass, field
from typing import Awaitable, Callable


@dataclass(frozen=True)
class ReportColumn:
    key: str
    label: str
    align: str = "left"


@dataclass(frozen=True)
class ReportFilter:
    field: str
    label: str
    type: str = "text"

    def to_schema(self) -> dict:
        return {"field": self.field, "label": self.label, "type": self.type}


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


@dataclass(frozen=True)
class ReportResult:
    definition: ReportDefinition
    rows: list[dict]

    def column_keys(self) -> list[str]:
        return [column.key for column in self.definition.columns]


class ReportRegistry:
    def __init__(self):
        self._definitions: dict[str, ReportDefinition] = {}

    def register(self, definition: ReportDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"report '{definition.name}' is already registered")

        self._definitions[definition.name] = definition

    def get(self, name: str) -> ReportDefinition:
        definition = self._definitions.get(name)

        if definition is None:
            raise KeyError(f"report '{name}' is not registered")

        return definition

    def names(self) -> list[str]:
        return list(self._definitions.keys())
