from sqlalchemy import select

from fastkit_accounts.models import User
from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    DateTimeField,
    NumberField,
    TextField,
)
from fastkit_admin.filters import (
    DateRangeFilter,
    LookupFilter,
)
from fastkit_admin.resource import AdminResource, Fieldset
from fastkit_content.models import Content, Language
from fastkit_logging.models import AuditLog
from fastkit_permissions.models import Role
from app.models import (
    Category,
    Product,
    Showcase,
    Subcategory,
)

from app.admin.helpers import (
    lookup_limit,
)


class ActivityLogAdmin(AdminResource[AuditLog]):
    name = "activity"
    label = "Activity log"
    icon = "history"
    model = AuditLog
    read_only = True

    list_columns = [
        "id",
        Column("created_at", type="datetime"),
        "action",
        "resource_type",
        "resource_id",
        "user_id",
    ]
    search_fields = ["resource_type", "action"]
    ordering = ["-created_at"]

    form_fields = [
        DateTimeField("created_at", label="When", readonly=True),
        TextField("action"),
        TextField("resource_type", label="Resource"),
        TextField("resource_id", label="Record"),
        NumberField("user_id", label="User"),
    ]

    permissions = {"list": "logs.view", "detail": "logs.view"}

    filters = [
        Fieldset("Period", ["created_at"]),
        Fieldset("Target", ["resource_type", "user_id"]),
        DateRangeFilter("created_at", label="Date"),
        LookupFilter("resource_type", label="Resource", options="resource_type"),
        LookupFilter("user_id", label="User", options="user_id"),
    ]

    RESOURCE_MODELS = {
        "users": User,
        "roles": Role,
        "categories": Category,
        "subcategories": Subcategory,
        "products": Product,
        "showcase": Showcase,
        "content": Content,
        "languages": Language,
    }

    async def resolve(self, session, rows, locale="en"):
        user_ids = {row.user_id for row in rows if row.user_id is not None}
        users = {}

        if user_ids:
            found = (
                (await session.execute(select(User).where(User.id.in_(user_ids))))
                .scalars()
                .all()
            )
            users = {user.id: user.display_label() for user in found}

        labels = {}

        for resource_type, model in self.RESOURCE_MODELS.items():
            ids = {
                int(row.resource_id)
                for row in rows
                if row.resource_type == resource_type
                and row.resource_id
                and row.resource_id.isdigit()
            }

            if not ids:
                continue

            records = (
                (await session.execute(select(model).where(model.id.in_(ids))))
                .scalars()
                .all()
            )

            for record in records:
                labels[(resource_type, str(record.id))] = (
                    record.display_label()
                    if hasattr(record, "display_label")
                    else str(record.id)
                )

        for row in rows:
            row._user_label = users.get(row.user_id)
            row._resource_label = labels.get((row.resource_type, row.resource_id))

    def render_user_id(self, row, locale):
        return getattr(row, "_user_label", None) or (
            str(row.user_id) if row.user_id is not None else None
        )

    def render_resource_id(self, row, locale):
        return getattr(row, "_resource_label", None) or row.resource_id

    async def options_resource_type(self, session, params, locale):
        types = (
            (await session.execute(select(AuditLog.resource_type).distinct()))
            .scalars()
            .all()
        )

        return [{"value": value, "label": value} for value in sorted(types)]

    async def options_user_id(self, session, params, locale):
        query = select(User)

        if params.get("value"):
            query = query.where(User.id == int(params["value"]))
        elif params.get("q"):
            query = query.where(User.display_name.ilike(f"%{params['q']}%"))

        rows = (
            (
                await session.execute(
                    query.order_by(User.display_name).limit(lookup_limit(params))
                )
            )
            .scalars()
            .all()
        )

        return [{"value": row.id, "label": row.display_label()} for row in rows]
