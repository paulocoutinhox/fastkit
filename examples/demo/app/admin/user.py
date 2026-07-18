from sqlalchemy import select

from fastkit_accounts.models import User
from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    BooleanField,
    EmailField,
    TextField,
)
from fastkit_admin.filters import (
    BooleanFilter,
    TextFilter,
)
from fastkit_admin.resource import AdminResource, Fieldset
from fastkit_tenancy.models import Tenant


class UserAdmin(AdminResource[User]):
    name = "users"
    label = "Users"
    icon = "users"
    model = User

    list_columns = [
        "id",
        "display_name",
        "email",
        Column("tenant", sortable=False),
        "status",
        "is_staff",
        Column("created_at", type="datetime"),
    ]
    search_fields = ["display_name", "email", "username"]
    filters = [
        TextFilter("email"),
        BooleanFilter("is_active"),
        BooleanFilter("is_staff"),
    ]
    ordering = ["-created_at"]

    async def resolve(self, session, rows, locale="en"):
        tenant_ids = {row.tenant_id for row in rows if row.tenant_id}
        tenants = {}

        if tenant_ids:
            found = (
                (await session.execute(select(Tenant).where(Tenant.id.in_(tenant_ids))))
                .scalars()
                .all()
            )
            tenants = {tenant.id: tenant.display_label() for tenant in found}

        for row in rows:
            row._tenant_label = tenants.get(row.tenant_id)

    def render_tenant(self, row, locale):
        return getattr(row, "_tenant_label", None) or "Global"

    form_fields = [
        TextField("display_name", label="Display name", required=True),
        EmailField("email", required=True),
        TextField("first_name", label="First name"),
        TextField("last_name", label="Last name"),
        BooleanField("is_active", label="Active"),
        BooleanField("is_staff", label="Staff"),
    ]

    fieldsets = [
        Fieldset("Identity", ["display_name", "email", "first_name", "last_name"]),
        Fieldset("Access", ["is_active", "is_staff"]),
    ]

    permissions = {
        "list": "users.view",
        "detail": "users.view",
        "create": "users.create",
        "update": "users.update",
        "delete": "users.delete",
    }

    def render_status(self, row, locale):
        label, tone = ("Active", "green") if row.is_active else ("Inactive", "red")

        return f'<span class="badge bg-{tone}-lt">{label}</span>'
