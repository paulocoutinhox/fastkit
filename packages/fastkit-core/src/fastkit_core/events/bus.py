import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

logger = logging.getLogger("fastkit.events")

Handler = Callable[["Event"], Awaitable[None]]


@dataclass
class Event:
    name: str
    payload: dict[str, Any]


@dataclass
class HandlerRegistration:
    name: str
    handler: Handler
    priority: int
    critical: bool
    timeout: float


class EventBus:
    """Ordered async event bus where non-critical handlers cannot break the main operation."""

    def __init__(self):
        self._handlers: dict[str, list[HandlerRegistration]] = {}

    def subscribe(self, event_name: str, handler: Handler, name: str, priority: int = 0, critical: bool = False, timeout: float = 5.0) -> None:
        registrations = self._handlers.setdefault(event_name, [])
        registrations.append(HandlerRegistration(name, handler, priority, critical, timeout))
        registrations.sort(key=lambda item: -item.priority)

    def handlers_for(self, event_name: str) -> list[HandlerRegistration]:
        return list(self._handlers.get(event_name, []))

    async def emit(self, event_name: str, **payload) -> None:
        event = Event(name=event_name, payload=payload)

        for registration in self.handlers_for(event_name):
            await self._run(registration, event)

    async def _run(self, registration: HandlerRegistration, event: Event) -> None:
        try:
            await asyncio.wait_for(registration.handler(event), timeout=registration.timeout)
        except Exception:
            logger.exception("event handler '%s' failed for '%s'", registration.name, event.name)

            if registration.critical:
                raise
