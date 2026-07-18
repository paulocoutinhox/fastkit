from dataclasses import dataclass

from fastkit_core.checks.base.level import CheckLevel


@dataclass(frozen=True)
class CheckMessage:
    level: CheckLevel
    message: str
    hint: str | None = None
