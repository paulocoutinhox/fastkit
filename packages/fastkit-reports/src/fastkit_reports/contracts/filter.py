from dataclasses import dataclass


@dataclass(frozen=True)
class ReportFilter:
    field: str
    label: str
    type: str = "text"

    def to_schema(self) -> dict:
        return {"field": self.field, "label": self.label, "type": self.type}
