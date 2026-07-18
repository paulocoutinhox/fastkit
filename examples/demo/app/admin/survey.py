from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    BooleanField,
    TextField,
)
from fastkit_admin.inlines import InlineResource
from fastkit_admin.resource import AdminResource
from app.models import (
    Survey,
    SurveyQuestion,
)


class SurveyAdmin(AdminResource[Survey]):
    name = "surveys"
    label = "Surveys"
    icon = "clipboard-list"
    model = Survey

    list_columns = ["id", "name", "is_active", Column("created_at", type="datetime")]
    search_fields = ["name"]
    ordering = ["name"]

    form_fields = [
        TextField("name", required=True, max_length=120),
        BooleanField("is_active", label="Active"),
    ]

    inlines = [
        InlineResource(
            "questions",
            [TextField("name", label="Question", required=True, max_length=200)],
            model=SurveyQuestion,
            fk_field="survey_id",
            label="Questions",
        )
    ]

    permissions = {
        "list": "products.view",
        "detail": "products.view",
        "create": "products.create",
        "update": "products.update",
        "delete": "products.delete",
    }
