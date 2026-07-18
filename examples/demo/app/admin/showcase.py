from datetime import datetime, timezone

from sqlalchemy import select

from fastkit_admin.actions import AdminAction
from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    BooleanField,
    ColorField,
    DateField,
    DateTimeField,
    DecimalField,
    EmailField,
    FileField,
    ImageField,
    JsonField,
    LookupField,
    MaskedField,
    MultiSelectField,
    NumberField,
    RichTextField,
    SelectField,
    TextareaField,
    TextField,
    TimeField,
    URLField,
)
from fastkit_admin.filters import (
    BooleanFilter,
    DateRangeFilter,
    EnumFilter,
    TextFilter,
)
from fastkit_admin.resource import AdminResource, Fieldset
from app.models import (
    Showcase,
)

from app.admin.helpers import (
    FILE_UPLOAD_URL,
    IMAGE_UPLOAD_URL,
    STATUS_CHOICES,
    TAG_CHOICES,
    category_options,
    subcategory_options,
)


class ShowcaseAdmin(AdminResource[Showcase]):
    name = "showcase"
    label = "Field showcase"
    icon = "sparkles"
    model = Showcase

    list_columns = [
        "id",
        "title",
        Column("quantity", align="center"),
        Column("price", align="right"),
        "status",
        "is_featured",
        "swatch",
        "release_date",
        Column("created_at", type="datetime"),
    ]
    file_fields = ["cover_url", "attachment_url"]
    search_fields = ["title", "summary"]
    filters = [
        TextFilter("title"),
        EnumFilter("status", choices=STATUS_CHOICES),
        BooleanFilter("is_featured"),
        DateRangeFilter("release_date"),
    ]
    actions = [
        AdminAction(
            name="publish", label="Publish", scope="bulk", permission="showcase.update"
        )
    ]
    ordering = ["-created_at"]

    form_fields = [
        TextField("title", required=True, max_length=160),
        TextareaField("summary", help_text="A short plain-text summary."),
        RichTextField("body_html", label="Body", upload_url=IMAGE_UPLOAD_URL),
        NumberField("quantity"),
        DecimalField("price", decimal_places=2),
        SelectField("status", choices=STATUS_CHOICES),
        MultiSelectField("tags", choices=TAG_CHOICES),
        LookupField("category_id", label="Category", related="categories"),
        LookupField(
            "subcategory_id",
            label="Subcategory",
            depends_on=["category_id"],
            related="subcategories",
        ),
        URLField("website", label="Website"),
        EmailField("contact_email", label="Contact email"),
        MaskedField(
            "reference_code",
            label="Reference code",
            mask="##-####-##",
            pattern=r"\d{2}-\d{4}-\d{2}",
        ),
        ColorField("brand_color", label="Brand color"),
        BooleanField("is_featured", label="Featured"),
        DateField("release_date", label="Release date"),
        TimeField("release_time", label="Release time"),
        DateTimeField("published_at", label="Published at"),
        JsonField("attributes"),
        ImageField("cover_url", label="Cover image", upload_url=IMAGE_UPLOAD_URL),
        FileField("attachment_url", label="Attachment", upload_url=FILE_UPLOAD_URL),
    ]

    fieldsets = [
        Fieldset("Content", ["title", "summary", "body_html"]),
        Fieldset("Pricing", ["quantity", "price"]),
        Fieldset("Classification", ["status", "tags", "category_id", "subcategory_id"]),
        Fieldset("Contact", ["website", "contact_email", "reference_code"]),
        Fieldset(
            "Presentation",
            ["brand_color", "is_featured", "cover_url", "attachment_url"],
        ),
        Fieldset("Scheduling", ["release_date", "release_time", "published_at"]),
        Fieldset("Advanced", ["attributes"]),
    ]

    permissions = {
        "list": "showcase.view",
        "detail": "showcase.view",
        "create": "showcase.create",
        "update": "showcase.update",
        "delete": "showcase.delete",
    }

    options_category_id = staticmethod(category_options)
    options_subcategory_id = staticmethod(subcategory_options)

    def get_queryset(self):
        return select(Showcase).where(Showcase.status != "archived")

    def sort_swatch(self):
        return Showcase.brand_color

    def render_swatch(self, row, locale):
        if not row.brand_color:
            return None

        return f'<span style="display:inline-block;width:1rem;height:1rem;border-radius:50%;background:{row.brand_color}"></span>'

    async def action_publish(self, session, rows, locale):
        for row in rows:
            row.status = "published"
            row.published_at = datetime.now(timezone.utc)

        await session.commit()

        return {"published": len(rows)}
