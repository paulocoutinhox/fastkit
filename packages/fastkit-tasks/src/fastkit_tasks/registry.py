from dataclasses import dataclass
from typing import Awaitable, Callable


class PermanentTaskError(Exception):
    """Raised by a handler to signal a non-retryable failure."""


@dataclass(frozen=True)
class TaskDefinition:
    name: str
    handler: Callable[..., Awaitable]
    queue: str
    max_attempts: int
    timeout: int
    retry_delay: int


class TaskRegistry:
    """Maps stable task names to their async handlers and execution policy."""

    def __init__(self):
        self._tasks: dict[str, TaskDefinition] = {}

    def register(self, definition: TaskDefinition) -> None:
        if definition.name in self._tasks:
            raise ValueError(f"task '{definition.name}' is already registered")

        self._tasks[definition.name] = definition

    def get(self, name: str) -> TaskDefinition:
        definition = self._tasks.get(name)

        if definition is None:
            raise KeyError(f"task '{name}' is not registered")

        return definition

    def contains(self, name: str) -> bool:
        return name in self._tasks

    def names(self) -> list[str]:
        return list(self._tasks.keys())

    def queues(self) -> list[str]:
        return sorted({definition.queue for definition in self._tasks.values()}) or ["default"]

    def task(self, name: str, queue: str = "default", max_attempts: int = 1, timeout: int = 60, retry_delay: int = 5):
        def decorator(handler):
            self.register(TaskDefinition(name=name, handler=handler, queue=queue, max_attempts=max_attempts, timeout=timeout, retry_delay=retry_delay))

            return handler

        return decorator
