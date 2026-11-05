"""What one dialect needs to drop a table other tables still point at."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DropDialect:
    disable: str
    enable: str
    cascade: bool = False
