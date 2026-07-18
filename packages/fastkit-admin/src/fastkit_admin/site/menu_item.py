from dataclasses import dataclass


@dataclass
class MenuItem:
    label: str
    group: str = "general"
    resource: str | None = None
    path: str | None = None
    icon: str = "dot"
    permission: str | None = None
    order: int = 0
