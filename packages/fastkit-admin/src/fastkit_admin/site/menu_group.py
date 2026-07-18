from dataclasses import dataclass


@dataclass
class MenuGroup:
    key: str
    label: str
    order: int = 0
    icon: str | None = None
