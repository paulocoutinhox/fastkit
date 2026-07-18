from typing import Callable

from fastkit_core.checks.base.error import SystemCheckError
from fastkit_core.checks.base.level import CheckLevel
from fastkit_core.checks.base.message import CheckMessage

SystemCheck = Callable[[], list[CheckMessage]]


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
