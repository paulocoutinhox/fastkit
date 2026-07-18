from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fastkit_admin.actions import AdminAction
from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    BooleanField,
    DateTimeField,
    DecimalField,
    ImageField,
    NumberField,
    RelationField,
    TextField,
)
from fastkit_admin.filters import (
    BooleanFilter,
    LookupFilter,
    TextFilter,
)
from fastkit_admin.resource import AdminResource, Fieldset
from app.models import (
    Product,
)

from app.admin.helpers import (
    IMAGE_UPLOAD_URL,
    category_options,
    cover_thumb,
    subcategory_options,
)


class ProductAdmin(AdminResource[Product]):
    name = "products"
    label = "Products"
    icon = "package"
    model = Product

    list_columns = [
        Column("image_url", label="Cover", sortable=False),
        "id",
        "name",
        "sku",
        Column("category", sortable=False),
        Column("subcategory", sortable=False),
        Column("price", align="right"),
        "is_active",
    ]
    search_fields = ["name", "sku"]
    file_fields = ["image_url"]
    filters = [
        Fieldset("Product", ["name", "is_active"]),
        Fieldset("Classification", ["category_id", "subcategory_id"]),
        TextFilter("name"),
        BooleanFilter("is_active"),
        LookupFilter("category_id", options="category_id", label="Category"),
        LookupFilter(
            "subcategory_id",
            options="subcategory_id",
            depends_on=["category_id"],
            label="Subcategory",
        ),
    ]
    actions = [
        AdminAction(
            name="deactivate",
            label="Deactivate",
            scope="bulk",
            permission="products.update",
            confirm=True,
            confirm_message="Deactivate the selected products?",
        )
    ]

    form_fields = [
        TextField("name", required=True, max_length=120),
        TextField("sku", required=True, max_length=40),
        ImageField("image_url", label="Cover", upload_url=IMAGE_UPLOAD_URL),
        DecimalField("price", required=True, decimal_places=2),
        RelationField("category_id", label="Category", related="categories"),
        RelationField(
            "subcategory_id",
            label="Subcategory",
            depends_on=["category_id"],
            related="subcategories",
        ),
        BooleanField("is_active", label="Active"),
        NumberField("id", label="ID", readonly=True),
        DateTimeField("created_at", label="Created at", readonly=True),
        DateTimeField("updated_at", label="Updated at", readonly=True),
    ]

    fieldsets = [
        Fieldset(
            "Details",
            ["name", "sku", "image_url", "price"],
            description="Basic product information.",
        ),
        Fieldset(
            "Classification",
            ["category_id", "subcategory_id"],
            description="Subcategory depends on the selected category.",
        ),
        Fieldset("Status", ["is_active"]),
        Fieldset(
            "Record",
            ["id", "created_at", "updated_at"],
            description="Read-only metadata shown on the detail screen.",
        ),
    ]

    permissions = {
        "list": "products.view",
        "detail": "products.view",
        "create": "products.create",
        "update": "products.update",
        "delete": "products.delete",
    }

    options_category_id = staticmethod(category_options)
    options_subcategory_id = staticmethod(subcategory_options)

    def get_queryset(self):
        return select(Product).options(
            selectinload(Product.category), selectinload(Product.subcategory)
        )

    def render_image_url(self, row, locale):
        return cover_thumb(row.image_url)

    def render_category(self, row, locale):
        return row.category.name if row.category else None

    def render_subcategory(self, row, locale):
        return row.subcategory.name if row.subcategory else None

    async def action_deactivate(self, session, rows, locale):
        for row in rows:
            row.is_active = False

        await session.commit()

        return {"deactivated": len(rows)}
