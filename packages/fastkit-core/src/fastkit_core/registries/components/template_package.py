from dataclasses import dataclass


@dataclass(frozen=True)
class TemplatePackage:
    package: str
    directory: str
    priority: int
    source: str
