from fastkit_admin.actions import AdminAction
from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    JsonField,
    TextField,
)
from fastkit_admin.filters import (
    EnumFilter,
)
from fastkit_admin.resource import AdminResource
from fastkit_tasks.models import TaskExecution

from app.admin.helpers import (
    STATUS_TONES,
    status_badge,
)


class TaskExecutionAdmin(AdminResource[TaskExecution]):
    name = "task-runs"
    label = "Task runs"
    icon = "list-check"
    model = TaskExecution
    read_only = True

    task_queue = None

    list_columns = [
        "id",
        "task_name",
        "queue",
        "status",
        "attempt_count",
        Column("started_at", type="datetime"),
        Column("finished_at", type="datetime"),
    ]
    search_fields = ["task_name"]
    filters = [
        EnumFilter("status", choices=[(value, value.title()) for value in STATUS_TONES])
    ]
    ordering = ["-created_at"]
    actions = [
        AdminAction(
            name="enqueue_email",
            label="Enqueue welcome email",
            scope="collection",
            variant="primary",
            icon="ti-mail",
            permission="tasks.view",
        )
    ]

    form_fields = [
        TextField("task_name", label="Task", readonly=True),
        TextField("queue", readonly=True),
        TextField("status", readonly=True),
        JsonField("payload", label="Payload"),
    ]
    permissions = {"list": "tasks.view", "detail": "tasks.view"}

    def display(self, row):
        return row.task_name

    def render_status(self, row, locale):
        return status_badge(row.status)

    async def action_enqueue_email(self, session, rows, locale):
        execution = await self.task_queue.enqueue(
            "demo.send_welcome_email",
            payload={"locale": locale, "template": "welcome"},
            queue="emails",
        )

        return {"enqueued": str(execution.id)}
