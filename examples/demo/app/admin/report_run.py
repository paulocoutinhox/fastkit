from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    JsonField,
    TextField,
)
from fastkit_admin.filters import (
    EnumFilter,
)
from fastkit_admin.resource import AdminResource
from fastkit_reports.models import ReportExecution

from app.admin.helpers import (
    STATUS_TONES,
    status_badge,
)


class ReportRunAdmin(AdminResource[ReportExecution]):
    name = "report-runs"
    label = "Report runs"
    icon = "report-analytics"
    model = ReportExecution
    read_only = True

    list_columns = [
        "id",
        "report_name",
        "status",
        "progress",
        "row_count",
        Column("created_at", type="datetime"),
        Column("finished_at", type="datetime"),
    ]
    search_fields = ["report_name"]
    filters = [
        EnumFilter("status", choices=[(value, value.title()) for value in STATUS_TONES])
    ]
    ordering = ["-created_at"]

    form_fields = [
        TextField("report_name", label="Report", readonly=True),
        TextField("status", readonly=True),
        JsonField("parameters", label="Parameters"),
    ]
    permissions = {"list": "reports.view", "detail": "reports.view"}

    def render_status(self, row, locale):
        return status_badge(row.status)
