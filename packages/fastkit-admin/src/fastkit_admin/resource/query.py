from dataclasses import dataclass, field


@dataclass
class GridQuery:
    page: int = 1
    page_size: int = 25
    search: str | None = None
    sort: str | None = None
    filters: dict = field(default_factory=dict)
