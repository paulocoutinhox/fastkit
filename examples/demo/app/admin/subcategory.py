from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    ImageField,
    RelationField,
    TextField,
)
from fastkit_admin.resource import AdminResource
from app.models import (
    Subcategory,
)

from app.admin.helpers import (
    IMAGE_UPLOAD_URL,
    category_options,
    cover_thumb,
)


class SubcategoryAdmin(AdminResource[Subcategory]):
    name = "subcategories"
    label = "Subcategories"
    icon = "sitemap"
    model = Subcategory

    list_columns = [
        Column("image_url", label="Cover", sortable=False),
        "id",
        "name",
        Column("created_at", type="datetime"),
    ]
    search_fields = ["name"]
    ordering = ["name"]
    file_fields = ["image_url"]

    form_fields = [
        TextField("name", required=True, max_length=80),
        ImageField("image_url", label="Cover", upload_url=IMAGE_UPLOAD_URL),
        RelationField("category_id", label="Category", required=True),
    ]

    permissions = {
        "list": "products.view",
        "detail": "products.view",
        "create": "products.create",
        "update": "products.update",
        "delete": "products.delete",
    }

    options_category_id = staticmethod(category_options)

    def render_image_url(self, row, locale):
        return cover_thumb(row.image_url)
