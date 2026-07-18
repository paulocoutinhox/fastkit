from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    """A grid column with alignment and sortability, optionally rendered by a resource method.

    Click-through to the edit form is decided by the resource's ``clickable_columns``, not per column.
    """

    name: str
    label: str | None = None
    align: str | None = None
    sortable: bool = True
    type: str | None = None

    def display_label(self) -> str:
        return self.label or self.name.replace("_", " ").title()

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "label": self.display_label(),
            "align": self.align,
            "sortable": self.sortable,
        }


def normalize_columns(columns: list) -> list[Column]:
    return [
        column if isinstance(column, Column) else Column(name=column)
        for column in columns
    ]
