# Events

`EventBus` (`fastkit_core.events`) is an in-process publish/subscribe bus for decoupling reactions
from actions.

```python
bus = context.component("event_bus")

async def on_user_created(event):
    ...

bus.subscribe("user.created", on_user_created)
await bus.emit("user.created", {"user_id": "42"})
```

## Snapshot iteration

`EventBus.emit` iterates a **snapshot** of the handlers (`handlers_for`), never the live handler
list — so a handler that subscribes or unsubscribes during dispatch can't corrupt the iteration.

## When to use it

Use the bus for cross-cutting reactions that must not couple the emitter to the reactor (send a
welcome email when a user is created, invalidate a cache when a record changes). For work that must
survive a restart or run out of band, enqueue a [task](../packages/tasks.md) instead — the bus is
in-process and best-effort.
