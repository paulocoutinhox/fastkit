from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateDirectory:
    path: str
    priority: int
    source: str
