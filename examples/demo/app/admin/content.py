from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    SelectField,
    TextField,
    TranslationsField,
)
from fastkit_admin.filters import (
    EnumFilter,
)
from fastkit_admin.resource import AdminResource, Fieldset
from fastkit_content.models import Content


class ContentAdmin(AdminResource[Content]):
    name = "content"
    label = "Content"
    icon = "file-text"
    model = Content

    list_columns = [
        "id",
        "key",
        "type",
        "status",
        Column("created_at", type="datetime"),
    ]
    search_fields = ["key"]
    filters = [
        EnumFilter(
            "status",
            choices=[
                ("draft", "Draft"),
                ("published", "Published"),
                ("archived", "Archived"),
            ],
        )
    ]
    ordering = ["-created_at"]

    form_fields = [
        TextField("key", required=True),
        SelectField(
            "type",
            choices=[
                ("rich_text", "Rich text"),
                ("html", "HTML"),
                ("plain_text", "Plain text"),
            ],
        ),
        TranslationsField(
            "translations",
            hide_label=True,
            languages_url="/content/languages",
            value_url="/content/{id}/translations",
            save_url="/content/{id}/translations",
        ),
    ]

    fieldsets = [
        Fieldset("Content", ["key", "type"]),
        Fieldset(
            "Translations",
            ["translations"],
            description="Edit the body for each active language.",
        ),
    ]

    permissions = {
        "list": "content.publish",
        "detail": "content.publish",
        "create": "content.publish",
        "update": "content.publish",
        "delete": "content.publish",
    }
