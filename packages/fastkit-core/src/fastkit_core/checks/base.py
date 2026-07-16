from dataclasses import dataclass
from enum import Enum
from typing import Callable


class CheckLevel(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


@dataclass(frozen=True)
class CheckMessage:
    level: CheckLevel
    message: str
    hint: str | None = None


SystemCheck = Callable[[], list[CheckMessage]]


class SystemCheckError(RuntimeError):
    pass


class SystemCheckRegistry:
    def __init__(self):
        self._checks: list[tuple[str, SystemCheck]] = []

    def register(self, name: str, check: SystemCheck) -> None:
        self._checks.append((name, check))

    def run(self) -> list[CheckMessage]:
        messages: list[CheckMessage] = []

        for _, check in self._checks:
            messages.extend(check())

        return messages

    def run_or_raise(self) -> list[CheckMessage]:
        messages = self.run()

        errors = [message for message in messages if message.level is CheckLevel.error]

        if errors:
            joined = "; ".join(item.message for item in errors)
            raise SystemCheckError(f"system checks failed: {joined}")

        return messages
