from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    BooleanField,
    ImageField,
    SelectField,
    TextField,
)
from fastkit_admin.filters import (
    BooleanFilter,
    EnumFilter,
)
from fastkit_admin.resource import AdminResource, Fieldset
from fastkit_tenancy.models import Tenant

from app.admin.helpers import (
    IMAGE_UPLOAD_URL,
)


class TenantAdmin(AdminResource[Tenant]):
    name = "tenants"
    label = "Tenants"
    icon = "building"
    model = Tenant

    list_columns = [
        "id",
        Column("image_url", label="Logo", sortable=False),
        "name",
        "code",
        "status",
        "default_locale",
        "is_active",
    ]
    search_fields = ["name", "code", "domain"]
    filters = [
        BooleanFilter("is_active"),
        EnumFilter(
            "status",
            choices=[
                ("active", "Active"),
                ("suspended", "Suspended"),
                ("disabled", "Disabled"),
            ],
        ),
    ]

    form_fields = [
        TextField("name", required=True),
        TextField("code", required=True),
        ImageField("image_url", label="Logo", upload_url=IMAGE_UPLOAD_URL),
        SelectField(
            "status",
            choices=[
                ("active", "Active"),
                ("suspended", "Suspended"),
                ("disabled", "Disabled"),
            ],
        ),
        TextField("default_locale", label="Default locale"),
        TextField("timezone"),
        TextField("domain"),
        BooleanField("is_active", label="Active"),
    ]
    fieldsets = [
        Fieldset(
            "Identity",
            ["name", "code", "image_url"],
            description="Tenant name and logo shown across the app.",
        ),
        Fieldset(
            "Preferences",
            ["status", "default_locale", "timezone", "domain", "is_active"],
            description="Per-tenant defaults.",
        ),
    ]
    permissions = {
        "list": "tenants.view",
        "detail": "tenants.view",
        "create": "tenants.manage",
        "update": "tenants.manage",
        "delete": "tenants.manage",
    }

    def display(self, row):
        return row.name

    def render_image_url(self, row, locale):
        if not row.image_url:
            return None

        return f'<img src="{row.image_url}" alt="logo" style="height:1.75rem;width:1.75rem;object-fit:cover;border-radius:6px">'
