import asyncio

import pytest

from fastkit_core.events.bus import EventBus


async def test_handlers_run_in_priority_order():
    bus = EventBus()
    calls: list[str] = []

    async def low(event):
        calls.append("low")

    async def high(event):
        calls.append("high")

    bus.subscribe("user.created", low, name="low", priority=1)
    bus.subscribe("user.created", high, name="high", priority=10)

    await bus.emit("user.created", user_id="1")

    assert calls == ["high", "low"]
    assert len(bus.handlers_for("user.created")) == 2


async def test_payload_is_passed():
    bus = EventBus()
    received: dict = {}

    async def handler(event):
        received.update(event.payload)
        received["name"] = event.name

    bus.subscribe("email.sent", handler, name="capture")
    await bus.emit("email.sent", to="a@b.c")

    assert received == {"to": "a@b.c", "name": "email.sent"}


async def test_non_critical_handler_failure_is_swallowed():
    bus = EventBus()

    async def broken(event):
        raise RuntimeError("boom")

    bus.subscribe("task.failed", broken, name="broken", critical=False)

    await bus.emit("task.failed")


async def test_critical_handler_failure_propagates():
    bus = EventBus()

    async def broken(event):
        raise RuntimeError("boom")

    bus.subscribe("task.failed", broken, name="broken", critical=True)

    with pytest.raises(RuntimeError, match="boom"):
        await bus.emit("task.failed")


async def test_timeout_is_treated_as_failure():
    bus = EventBus()

    async def slow(event):
        await asyncio.sleep(1)

    bus.subscribe("app.started", slow, name="slow", timeout=0.01)

    await bus.emit("app.started")


async def test_emit_without_handlers_is_noop():
    bus = EventBus()

    await bus.emit("nothing.here")
