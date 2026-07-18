from dataclasses import dataclass

from fastkit_reports.contracts.definition import ReportDefinition


@dataclass(frozen=True)
class ReportResult:
    definition: ReportDefinition
    rows: list[dict]

    def column_keys(self) -> list[str]:
        return [column.key for column in self.definition.columns]
