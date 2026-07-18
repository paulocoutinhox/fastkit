from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fastkit_accounts.models import User
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
    PermissionMatrixField,
    RelationField,
    RichTextField,
    SelectField,
    TextareaField,
    TextField,
    TimeField,
    TranslationsField,
    URLField,
)
from fastkit_admin.filters import (
    BooleanFilter,
    DateRangeFilter,
    EnumFilter,
    LookupFilter,
    SelectFilter,
    TextFilter,
)
from fastkit_admin.inlines import InlineResource
from fastkit_admin.resource import AdminResource, Fieldset
from app.geo import city_options, country_options, district_options, grid_delay, state_options
from fastkit_content.models import Content, Language
from fastkit_logging.models import AuditLog
from fastkit_permissions.models import Role
from fastkit_reports.models import ReportExecution
from fastkit_tasks.models import ScheduledTask, TaskExecution
from fastkit_tenancy.models import Tenant
from app.models import Category, GeoSample, Product, Showcase, Subcategory

IMAGE_UPLOAD_URL = "/api/uploads/image"
FILE_UPLOAD_URL = "/api/uploads/file"

STATUS_CHOICES = [("draft", "Draft"), ("published", "Published"), ("archived", "Archived")]
TAG_CHOICES = [("new", "New"), ("sale", "Sale"), ("featured", "Featured"), ("limited", "Limited")]


def lookup_limit(params):
    return max(1, min(int(params.get("limit", 20)), 50))


async def category_options(session, params, locale):
    query = select(Category).where(Category.is_active.is_(True))

    if params.get("value"):
        query = query.where(Category.id == int(params["value"]))
    elif params.get("q"):
        query = query.where(Category.name.ilike(f"%{params['q']}%"))

    rows = (await session.execute(query.order_by(Category.name).limit(lookup_limit(params)))).scalars().all()

    return [{"value": row.id, "label": row.name} for row in rows]


async def subcategory_options(session, params, locale):
    if params.get("value"):
        rows = (await session.execute(select(Subcategory).where(Subcategory.id == int(params["value"])))).scalars().all()

        return [{"value": row.id, "label": row.name} for row in rows]

    category_id = params.get("category_id")

    if not category_id:
        return []

    query = select(Subcategory).where(Subcategory.category_id == int(category_id))

    if params.get("q"):
        query = query.where(Subcategory.name.ilike(f"%{params['q']}%"))

    rows = (await session.execute(query.order_by(Subcategory.name).limit(lookup_limit(params)))).scalars().all()

    return [{"value": row.id, "label": row.name} for row in rows]


def cover_thumb(value):
    if not value:
        return None

    return f'<img src="{value}" alt="cover" style="height:2rem;width:2rem;object-fit:cover;border-radius:6px">'


class UserAdmin(AdminResource[User]):
    name = "users"
    label = "Users"
    icon = "users"
    model = User

    list_columns = ["id", "display_name", "email", Column("tenant", sortable=False), "status", "is_staff", Column("created_at", type="datetime")]
    search_fields = ["display_name", "email", "username"]
    filters = [TextFilter("email"), BooleanFilter("is_active"), BooleanFilter("is_staff")]
    ordering = ["-created_at"]

    async def resolve(self, session, rows, locale="en"):
        tenant_ids = {row.tenant_id for row in rows if row.tenant_id}
        tenants = {}

        if tenant_ids:
            found = (await session.execute(select(Tenant).where(Tenant.id.in_(tenant_ids)))).scalars().all()
            tenants = {tenant.id: tenant.display_label() for tenant in found}

        for row in rows:
            row._tenant_label = tenants.get(row.tenant_id)

    def render_tenant(self, row, locale):
        return getattr(row, "_tenant_label", None) or "Global"

    form_fields = [
        TextField("display_name", label="Display name", required=True),
        EmailField("email", required=True),
        TextField("first_name", label="First name"),
        TextField("last_name", label="Last name"),
        BooleanField("is_active", label="Active"),
        BooleanField("is_staff", label="Staff"),
    ]

    fieldsets = [
        Fieldset("Identity", ["display_name", "email", "first_name", "last_name"]),
        Fieldset("Access", ["is_active", "is_staff"]),
    ]

    permissions = {"list": "users.view", "detail": "users.view", "create": "users.create", "update": "users.update", "delete": "users.delete"}

    def render_status(self, row, locale):
        label, tone = ("Active", "green") if row.is_active else ("Inactive", "red")

        return f'<span class="badge bg-{tone}-lt">{label}</span>'


class CategoryAdmin(AdminResource[Category]):
    name = "categories"
    label = "Categories"
    icon = "folder"
    model = Category

    list_columns = [Column("image_url", label="Cover", sortable=False), "id", "name", "is_active", Column("created_at", type="datetime")]
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

    inlines = [
        InlineResource(
            "subcategories",
            [TextField("name", label="Name", required=True, max_length=80)],
            model=Subcategory,
            fk_field="category_id",
            label="Subcategories",
        )
    ]

    permissions = {"list": "products.view", "detail": "products.view", "create": "products.create", "update": "products.update", "delete": "products.delete"}


class SubcategoryAdmin(AdminResource[Subcategory]):
    name = "subcategories"
    label = "Subcategories"
    icon = "sitemap"
    model = Subcategory

    list_columns = [Column("image_url", label="Cover", sortable=False), "id", "name", Column("created_at", type="datetime")]
    search_fields = ["name"]
    ordering = ["name"]
    file_fields = ["image_url"]

    form_fields = [
        TextField("name", required=True, max_length=80),
        ImageField("image_url", label="Cover", upload_url=IMAGE_UPLOAD_URL),
        RelationField("category_id", label="Category", required=True),
    ]

    permissions = {"list": "products.view", "detail": "products.view", "create": "products.create", "update": "products.update", "delete": "products.delete"}

    options_category_id = staticmethod(category_options)

    def render_image_url(self, row, locale):
        return cover_thumb(row.image_url)


class ProductAdmin(AdminResource[Product]):
    name = "products"
    label = "Products"
    icon = "package"
    model = Product

    list_columns = [Column("image_url", label="Cover", sortable=False), "id", "name", "sku", Column("category", sortable=False), Column("subcategory", sortable=False), Column("price", align="right"), "is_active"]
    search_fields = ["name", "sku"]
    file_fields = ["image_url"]
    filters = [
        Fieldset("Product", ["name", "is_active"]),
        Fieldset("Classification", ["category_id", "subcategory_id"]),
        TextFilter("name"),
        BooleanFilter("is_active"),
        LookupFilter("category_id", options="category_id", label="Category"),
        LookupFilter("subcategory_id", options="subcategory_id", depends_on=["category_id"], label="Subcategory"),
    ]
    actions = [AdminAction(name="deactivate", label="Deactivate", scope="bulk", permission="products.update", confirm=True, confirm_message="Deactivate the selected products?")]

    form_fields = [
        TextField("name", required=True, max_length=120),
        TextField("sku", required=True, max_length=40),
        ImageField("image_url", label="Cover", upload_url=IMAGE_UPLOAD_URL),
        DecimalField("price", required=True, decimal_places=2),
        RelationField("category_id", label="Category", related="categories"),
        RelationField("subcategory_id", label="Subcategory", depends_on=["category_id"], related="subcategories"),
        BooleanField("is_active", label="Active"),
        NumberField("id", label="ID", readonly=True),
        DateTimeField("created_at", label="Created at", readonly=True),
        DateTimeField("updated_at", label="Updated at", readonly=True),
    ]

    fieldsets = [
        Fieldset("Details", ["name", "sku", "image_url", "price"], description="Basic product information."),
        Fieldset("Classification", ["category_id", "subcategory_id"], description="Subcategory depends on the selected category."),
        Fieldset("Status", ["is_active"]),
        Fieldset("Record", ["id", "created_at", "updated_at"], description="Read-only metadata shown on the detail screen."),
    ]

    permissions = {"list": "products.view", "detail": "products.view", "create": "products.create", "update": "products.update", "delete": "products.delete"}

    options_category_id = staticmethod(category_options)
    options_subcategory_id = staticmethod(subcategory_options)

    def get_queryset(self):
        return select(Product).options(selectinload(Product.category), selectinload(Product.subcategory))

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
    actions = [AdminAction(name="publish", label="Publish", scope="bulk", permission="showcase.update")]
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
        LookupField("subcategory_id", label="Subcategory", depends_on=["category_id"], related="subcategories"),
        URLField("website", label="Website"),
        EmailField("contact_email", label="Contact email"),
        MaskedField("reference_code", label="Reference code", mask="##-####-##", pattern=r"\d{2}-\d{4}-\d{2}"),
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
        Fieldset("Presentation", ["brand_color", "is_featured", "cover_url", "attachment_url"]),
        Fieldset("Scheduling", ["release_date", "release_time", "published_at"]),
        Fieldset("Advanced", ["attributes"]),
    ]

    permissions = {"list": "showcase.view", "detail": "showcase.view", "create": "showcase.create", "update": "showcase.update", "delete": "showcase.delete"}

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


class GeoSampleAdmin(AdminResource[GeoSample]):
    name = "geo-samples"
    label = "Geo samples"
    icon = "map-pin"
    model = GeoSample

    list_columns = ["id", "name", "sel_country", "sel_state", "sel_city", Column("created_at", type="datetime")]
    search_fields = ["name"]
    ordering = ["-created_at"]

    filters = [
        Fieldset("Dependent selects", ["sel_country", "sel_state", "sel_city", "sel_district"]),
        Fieldset("Dependent lookups", ["look_country", "look_state", "look_city", "look_district"]),
        SelectFilter("sel_country", options="sel_country", label="Country (select)"),
        SelectFilter("sel_state", options="sel_state", depends_on=["sel_country"], label="State (select)"),
        SelectFilter("sel_city", options="sel_city", depends_on=["sel_state"], label="City (select)"),
        SelectFilter("sel_district", options="sel_district", depends_on=["sel_city"], label="District (select)"),
        LookupFilter("look_country", options="look_country", label="Country (lookup)"),
        LookupFilter("look_state", options="look_state", depends_on=["look_country"], label="State (lookup)"),
        LookupFilter("look_city", options="look_city", depends_on=["look_state"], label="City (lookup)"),
        LookupFilter("look_district", options="look_district", depends_on=["look_city"], label="District (lookup)"),
    ]

    form_fields = [
        TextField("name", required=True, max_length=120),
        RelationField("sel_country", label="Country (select)"),
        RelationField("sel_state", label="State (select)", depends_on=["sel_country"]),
        RelationField("sel_city", label="City (select)", depends_on=["sel_state"]),
        RelationField("sel_district", label="District (select)", depends_on=["sel_city"]),
        LookupField("look_country", label="Country (lookup)"),
        LookupField("look_state", label="State (lookup)", depends_on=["look_country"]),
        LookupField("look_city", label="City (lookup)", depends_on=["look_state"]),
        LookupField("look_district", label="District (lookup)", depends_on=["look_city"]),
    ]

    fieldsets = [
        Fieldset("Details", ["name"]),
        Fieldset("Dependent selects", ["sel_country", "sel_state", "sel_city", "sel_district"], description="A four-level country → state → city → district chain, each loaded from a deliberately slow remote source."),
        Fieldset("Dependent lookups", ["look_country", "look_state", "look_city", "look_district"], description="The same four-level chain rendered as autocomplete lookups."),
    ]

    permissions = {"list": "products.view", "detail": "products.view", "create": "products.create", "update": "products.update", "delete": "products.delete"}

    options_sel_country = staticmethod(country_options())
    options_sel_state = staticmethod(state_options("sel_country"))
    options_sel_city = staticmethod(city_options("sel_state"))
    options_sel_district = staticmethod(district_options("sel_city"))
    options_look_country = staticmethod(country_options())
    options_look_state = staticmethod(state_options("look_country"))
    options_look_city = staticmethod(city_options("look_state"))
    options_look_district = staticmethod(district_options("look_city"))

    async def list(self, session, query, locale="en"):
        await grid_delay()

        return await super().list(session, query, locale)


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
        Fieldset("Permissions", ["permissions_matrix"], description="Check the permissions this role grants, grouped by module."),
    ]

    permissions = {"list": "roles.manage", "detail": "roles.manage", "create": "roles.manage", "update": "roles.manage", "delete": "roles.manage"}


class LanguageAdmin(AdminResource[Language]):
    name = "languages"
    label = "Languages"
    icon = "language"
    model = Language

    list_columns = ["id", "code", "name", "native_name", "is_active", "is_default", "sort_order"]
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

    permissions = {"list": "content.publish", "detail": "content.publish", "create": "content.publish", "update": "content.publish", "delete": "content.publish"}


class ContentAdmin(AdminResource[Content]):
    name = "content"
    label = "Content"
    icon = "file-text"
    model = Content

    list_columns = ["id", "key", "type", "status", Column("created_at", type="datetime")]
    search_fields = ["key"]
    filters = [EnumFilter("status", choices=[("draft", "Draft"), ("published", "Published"), ("archived", "Archived")])]
    ordering = ["-created_at"]

    form_fields = [
        TextField("key", required=True),
        SelectField("type", choices=[("rich_text", "Rich text"), ("html", "HTML"), ("plain_text", "Plain text")]),
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
        Fieldset("Translations", ["translations"], description="Edit the body for each active language."),
    ]

    permissions = {"list": "content.publish", "detail": "content.publish", "create": "content.publish", "update": "content.publish", "delete": "content.publish"}


class ActivityLogAdmin(AdminResource[AuditLog]):
    name = "activity"
    label = "Activity log"
    icon = "history"
    model = AuditLog
    read_only = True

    list_columns = ["id", Column("created_at", type="datetime"), "action", "resource_type", "resource_id", "user_id"]
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

    RESOURCE_MODELS = {"users": User, "roles": Role, "categories": Category, "subcategories": Subcategory, "products": Product, "showcase": Showcase, "content": Content, "languages": Language}

    async def resolve(self, session, rows, locale="en"):
        user_ids = {row.user_id for row in rows if row.user_id is not None}
        users = {}

        if user_ids:
            found = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
            users = {user.id: user.display_label() for user in found}

        labels = {}

        for resource_type, model in self.RESOURCE_MODELS.items():
            ids = {int(row.resource_id) for row in rows if row.resource_type == resource_type and row.resource_id and row.resource_id.isdigit()}

            if not ids:
                continue

            records = (await session.execute(select(model).where(model.id.in_(ids)))).scalars().all()

            for record in records:
                labels[(resource_type, str(record.id))] = record.display_label() if hasattr(record, "display_label") else str(record.id)

        for row in rows:
            row._user_label = users.get(row.user_id)
            row._resource_label = labels.get((row.resource_type, row.resource_id))

    def render_user_id(self, row, locale):
        return getattr(row, "_user_label", None) or (str(row.user_id) if row.user_id is not None else None)

    def render_resource_id(self, row, locale):
        return getattr(row, "_resource_label", None) or row.resource_id

    async def options_resource_type(self, session, params, locale):
        types = (await session.execute(select(AuditLog.resource_type).distinct())).scalars().all()

        return [{"value": value, "label": value} for value in sorted(types)]

    async def options_user_id(self, session, params, locale):
        query = select(User)

        if params.get("value"):
            query = query.where(User.id == int(params["value"]))
        elif params.get("q"):
            query = query.where(User.display_name.ilike(f"%{params['q']}%"))

        rows = (await session.execute(query.order_by(User.display_name).limit(lookup_limit(params)))).scalars().all()

        return [{"value": row.id, "label": row.display_label()} for row in rows]


STATUS_TONES = {"succeeded": "green", "running": "azure", "retrying": "yellow", "pending": "secondary", "failed": "red", "cancelled": "secondary"}


def status_badge(value):
    tone = STATUS_TONES.get(value, "secondary")

    return f'<span class="badge bg-{tone}-lt">{value}</span>'


class TenantAdmin(AdminResource[Tenant]):
    name = "tenants"
    label = "Tenants"
    icon = "building"
    model = Tenant

    list_columns = ["id", Column("image_url", label="Logo", sortable=False), "name", "code", "status", "default_locale", "is_active"]
    search_fields = ["name", "code", "domain"]
    filters = [BooleanFilter("is_active"), EnumFilter("status", choices=[("active", "Active"), ("suspended", "Suspended"), ("disabled", "Disabled")])]

    form_fields = [
        TextField("name", required=True),
        TextField("code", required=True),
        ImageField("image_url", label="Logo", upload_url=IMAGE_UPLOAD_URL),
        SelectField("status", choices=[("active", "Active"), ("suspended", "Suspended"), ("disabled", "Disabled")]),
        TextField("default_locale", label="Default locale"),
        TextField("timezone"),
        TextField("domain"),
        BooleanField("is_active", label="Active"),
    ]
    fieldsets = [
        Fieldset("Identity", ["name", "code", "image_url"], description="Tenant name and logo shown across the app."),
        Fieldset("Preferences", ["status", "default_locale", "timezone", "domain", "is_active"], description="Per-tenant defaults."),
    ]
    permissions = {"list": "tenants.view", "detail": "tenants.view", "create": "tenants.manage", "update": "tenants.manage", "delete": "tenants.manage"}

    def display(self, row):
        return row.name

    def render_image_url(self, row, locale):
        if not row.image_url:
            return None

        return f'<img src="{row.image_url}" alt="logo" style="height:1.75rem;width:1.75rem;object-fit:cover;border-radius:6px">'


class ScheduledTaskAdmin(AdminResource[ScheduledTask]):
    name = "scheduled-tasks"
    label = "Scheduled tasks"
    icon = "clock-play"
    model = ScheduledTask
    read_only = True

    list_columns = ["id", "name", "task_name", "schedule_type", "queue", "enabled", Column("next_run_at", type="datetime"), Column("last_run_at", type="datetime")]
    search_fields = ["name", "task_name"]
    filters = [BooleanFilter("enabled"), EnumFilter("schedule_type", choices=[("cron", "Cron"), ("interval", "Interval"), ("once", "Once")])]
    ordering = ["name"]

    form_fields = [
        TextField("name", label="Name", readonly=True),
        TextField("task_name", label="Task", readonly=True),
        TextField("schedule_type", label="Schedule", readonly=True),
        TextField("queue", readonly=True),
        JsonField("payload", label="Payload"),
    ]
    permissions = {"list": "tasks.view", "detail": "tasks.view"}

    def display(self, row):
        return row.name


class TaskExecutionAdmin(AdminResource[TaskExecution]):
    name = "task-runs"
    label = "Task runs"
    icon = "list-check"
    model = TaskExecution
    read_only = True

    task_queue = None

    list_columns = ["id", "task_name", "queue", "status", "attempt_count", Column("started_at", type="datetime"), Column("finished_at", type="datetime")]
    search_fields = ["task_name"]
    filters = [EnumFilter("status", choices=[(value, value.title()) for value in STATUS_TONES])]
    ordering = ["-created_at"]
    actions = [AdminAction(name="enqueue_email", label="Enqueue welcome email", scope="collection", variant="primary", icon="ti-mail", permission="tasks.view")]

    form_fields = [
        TextField("task_name", label="Task", readonly=True),
        TextField("queue", readonly=True),
        TextField("status", readonly=True),
        JsonField("payload", label="Payload"),
    ]
    permissions = {"list": "tasks.view", "detail": "tasks.view"}

    def display(self, row):
        return row.task_name

    def render_status(self, row, locale):
        return status_badge(row.status)

    async def action_enqueue_email(self, session, rows, locale):
        execution = await self.task_queue.enqueue("demo.send_welcome_email", payload={"locale": locale, "template": "welcome"}, queue="emails")

        return {"enqueued": str(execution.id)}


class ReportRunAdmin(AdminResource[ReportExecution]):
    name = "report-runs"
    label = "Report runs"
    icon = "report-analytics"
    model = ReportExecution
    read_only = True

    list_columns = ["id", "report_name", "status", "progress", "row_count", Column("created_at", type="datetime"), Column("finished_at", type="datetime")]
    search_fields = ["report_name"]
    filters = [EnumFilter("status", choices=[(value, value.title()) for value in STATUS_TONES])]
    ordering = ["-created_at"]

    form_fields = [
        TextField("report_name", label="Report", readonly=True),
        TextField("status", readonly=True),
        JsonField("parameters", label="Parameters"),
    ]
    permissions = {"list": "reports.view", "detail": "reports.view"}

    def render_status(self, row, locale):
        return status_badge(row.status)


ADMIN_RESOURCES = [UserAdmin, CategoryAdmin, SubcategoryAdmin, ProductAdmin, ShowcaseAdmin, GeoSampleAdmin, TenantAdmin, RoleAdmin, LanguageAdmin, ContentAdmin, ScheduledTaskAdmin, TaskExecutionAdmin, ReportRunAdmin, ActivityLogAdmin]
