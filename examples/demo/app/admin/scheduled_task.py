from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    JsonField,
    TextField,
)
from fastkit_admin.filters import (
    BooleanFilter,
    EnumFilter,
)
from fastkit_admin.resource import AdminResource
from fastkit_tasks.models import ScheduledTask


class ScheduledTaskAdmin(AdminResource[ScheduledTask]):
    name = "scheduled-tasks"
    label = "Scheduled tasks"
    icon = "clock-play"
    model = ScheduledTask
    read_only = True

    list_columns = [
        "id",
        "name",
        "task_name",
        "schedule_type",
        "queue",
        "enabled",
        Column("next_run_at", type="datetime"),
        Column("last_run_at", type="datetime"),
    ]
    search_fields = ["name", "task_name"]
    filters = [
        BooleanFilter("enabled"),
        EnumFilter(
            "schedule_type",
            choices=[("cron", "Cron"), ("interval", "Interval"), ("once", "Once")],
        ),
    ]
    ordering = ["name"]

    form_fields = [
        TextField("name", label="Name", readonly=True),
        TextField("task_name", label="Task", readonly=True),
        TextField("schedule_type", label="Schedule", readonly=True),
        TextField("queue", readonly=True),
        JsonField("payload", label="Payload"),
    ]
    permissions = {"list": "tasks.view", "detail": "tasks.view"}

    def display(self, row):
        return row.name
