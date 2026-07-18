# Add a custom action

Declare an `AdminAction` and implement its `action_<name>` method.

```python
from fastkit_admin.actions import AdminAction

class OrderAdmin(AdminResource[Order]):
    actions = [
        AdminAction(name="mark_shipped", label="Mark shipped", scope="bulk", confirm=True),
        AdminAction(name="export_invoices", label="Export invoices", scope="collection"),
    ]

    async def action_mark_shipped(self, session, ids, locale):
        for order_id in ids:
            order = await self.get_object(session, order_id)
            order.status = "shipped"
        await session.commit()
        return {"updated": len(ids)}

    async def action_export_invoices(self, session, ids, locale):
        # collection action → ids is empty; act on the whole set
        ...
```

## Scope reminders

- `row` → runs on one record (row `⋮` menu).
- `bulk` → runs on the selected ids (toolbar dropdown).
- `collection` → runs with no selection (toolbar button).

Set `confirm=True` for anything destructive (the client wraps it in `FastKit.confirm`). See
[Actions](../admin/actions.md).

## Record an audit entry

```python
async def action_mark_shipped(self, session, ids, locale):
    ...
    for order_id in ids:
        await self.audit("mark_shipped", "orders", str(order_id))
```

Test the `action_<name>` method directly, and add an e2e for the button + confirmation flow.
