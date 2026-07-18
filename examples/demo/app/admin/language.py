from fastkit_admin.fields import (
    BooleanField,
    NumberField,
    TextField,
)
from fastkit_admin.filters import (
    BooleanFilter,
)
from fastkit_admin.resource import AdminResource
from fastkit_content.models import Language


class LanguageAdmin(AdminResource[Language]):
    name = "languages"
    label = "Languages"
    icon = "language"
    model = Language

    list_columns = [
        "id",
        "code",
        "name",
        "native_name",
        "is_active",
        "is_default",
        "sort_order",
    ]
    search_fields = ["code", "name"]
    filters = [BooleanFilter("is_active")]
    ordering = ["sort_order", "code"]

    form_fields = [
        TextField("code", required=True, max_length=12),
        TextField("name", required=True, max_length=120),
        TextField("native_name", label="Native name", required=True, max_length=120),
        BooleanField("is_active", label="Active"),
        NumberField("sort_order", label="Sort order"),
    ]

    permissions = {
        "list": "content.publish",
        "detail": "content.publish",
        "create": "content.publish",
        "update": "content.publish",
        "delete": "content.publish",
    }
