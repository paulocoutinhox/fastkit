from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    BooleanField,
    ImageField,
    TextField,
)
from fastkit_admin.filters import (
    BooleanFilter,
)
from fastkit_admin.resource import AdminResource
from app.models import (
    Category,
)

from app.admin.helpers import (
    IMAGE_UPLOAD_URL,
    cover_thumb,
)


class CategoryAdmin(AdminResource[Category]):
    name = "categories"
    label = "Categories"
    icon = "folder"
    model = Category

    list_columns = [
        Column("image_url", label="Cover", sortable=False),
        "id",
        "name",
        "is_active",
        Column("created_at", type="datetime"),
    ]
    clickable_columns = ["name"]
    search_fields = ["name"]
    filters = [BooleanFilter("is_active")]
    ordering = ["name"]
    file_fields = ["image_url"]

    form_fields = [
        TextField("name", required=True, max_length=80),
        ImageField("image_url", label="Cover", upload_url=IMAGE_UPLOAD_URL),
        BooleanField("is_active", label="Active"),
    ]

    def render_image_url(self, row, locale):
        return cover_thumb(row.image_url)

    permissions = {
        "list": "products.view",
        "detail": "products.view",
        "create": "products.create",
        "update": "products.update",
        "delete": "products.delete",
    }
