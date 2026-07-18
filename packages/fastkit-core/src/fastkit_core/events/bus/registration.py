from dataclasses import dataclass
from typing import Awaitable, Callable

from fastkit_core.events.bus.event import Event

Handler = Callable[[Event], Awaitable[None]]


@dataclass
class HandlerRegistration:
    name: str
    handler: Handler
    priority: int
    critical: bool
    timeout: float
