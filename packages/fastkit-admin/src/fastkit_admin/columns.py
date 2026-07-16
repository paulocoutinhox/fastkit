from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    """A grid column with alignment, sortability and click-through, optionally rendered by a resource method."""

    name: str
    label: str | None = None
    align: str | None = None
    sortable: bool = True
    clickable: bool = False
    type: str | None = None

    def display_label(self) -> str:
        return self.label or self.name.replace("_", " ").title()

    def to_schema(self) -> dict:
        return {"name": self.name, "label": self.display_label(), "align": self.align, "sortable": self.sortable, "clickable": self.clickable}


def normalize_columns(columns: list) -> list[Column]:
    return [column if isinstance(column, Column) else Column(name=column) for column in columns]
