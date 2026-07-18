from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(frozen=True)
class TaskDefinition:
    name: str
    handler: Callable[..., Awaitable]
    queue: str
    max_attempts: int
    timeout: int
    retry_delay: int
