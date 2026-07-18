from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    PermissionMatrixField,
    TextField,
)
from fastkit_admin.resource import AdminResource, Fieldset
from fastkit_permissions.models import Role


class RoleAdmin(AdminResource[Role]):
    name = "roles"
    label = "Roles"
    icon = "shield"
    model = Role

    list_columns = ["id", "name", "description", Column("created_at", type="datetime")]
    search_fields = ["name"]
    ordering = ["name"]

    form_fields = [
        TextField("name", required=True),
        TextField("description"),
        PermissionMatrixField(
            "permissions_matrix",
            hide_label=True,
            groups_url="/meta/permissions",
            value_url="/roles/{id}/permissions",
            save_url="/roles/{id}/permissions",
        ),
    ]

    fieldsets = [
        Fieldset("Role", ["name", "description"]),
        Fieldset(
            "Permissions",
            ["permissions_matrix"],
            description="Check the permissions this role grants, grouped by module.",
        ),
    ]

    permissions = {
        "list": "roles.manage",
        "detail": "roles.manage",
        "create": "roles.manage",
        "update": "roles.manage",
        "delete": "roles.manage",
    }
