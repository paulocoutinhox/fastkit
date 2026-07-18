# Admin actions

Actions add operations beyond CRUD. There are three scopes.

```python
from fastkit_admin.actions import AdminAction

class TaskAdmin(AdminResource[Task]):
    actions = [
        AdminAction(name="deactivate", label="Deactivate", scope="bulk", confirm=True),
        AdminAction(name="enqueue_welcome", label="Enqueue welcome email", scope="collection"),
        AdminAction(name="retry", label="Retry", scope="row"),
    ]

    async def action_deactivate(self, session, ids, locale):
        ...

    async def action_enqueue_welcome(self, session, ids, locale):
        ...   # ids is empty for collection actions
```

Each action needs an `action_<name>` method, or `run_action` raises `NotFound`.

## Scopes

| Scope | Renders as | Runs with |
|---|---|---|
| `row` | An item in the row `⋮` dropdown. | that one record. |
| `bulk` | An item in the toolbar bulk dropdown (shown when rows are selected). | the selected ids. |
| `collection` | A toolbar button (no selection needed). | no ids. |

The demo's Task resource runs an "Enqueue welcome email" collection action that enqueues a
`fastkit-tasks` job.

## Standard row actions

The row `⋮` dropdown also shows **View** (`can_detail`), **Edit** (`can_update`), your custom row
actions, extension actions, and **Delete** (`can_delete`) — all permission-gated.

## Confirmation

Set `confirm=True` and every destructive run goes behind `FastKit.confirm` on the client.

## Audit

After create/update/delete the admin calls `AdminDeps.audit(action, resource_type, resource_id)` — see
[Permissions](permissions.md). Custom actions can record their own audit entries.

## Extending from the client

External scripts register interactive row actions via `FastKitAdmin.registerRowAction` and refresh a
row or the whole grid — see [Client (app.js)](client-js.md) and
[Extend the admin client](../guides/extend-admin-client.md).
