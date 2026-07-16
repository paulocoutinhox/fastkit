from datetime import date, datetime, time, timezone
from decimal import Decimal

from fastkit_db.base import Base
from fastkit_reports.models import ReportExecution
from fastkit_tasks.models import ScheduledTask, TaskExecution
from fastkit_tenancy.models import Tenant
from app.models import Category, Product, Showcase, Subcategory

PERMISSIONS = [
    ("users.view", "View users", "Users"),
    ("users.create", "Create users", "Users"),
    ("users.update", "Update users", "Users"),
    ("users.delete", "Delete users", "Users"),
    ("products.view", "View products", "Products"),
    ("products.create", "Create products", "Products"),
    ("products.update", "Update products", "Products"),
    ("products.delete", "Delete products", "Products"),
    ("showcase.view", "View showcase", "Showcase"),
    ("showcase.create", "Create showcase", "Showcase"),
    ("showcase.update", "Update showcase", "Showcase"),
    ("showcase.delete", "Delete showcase", "Showcase"),
    ("roles.manage", "Manage roles", "Access control"),
    ("logs.view", "View activity log", "Access control"),
    ("content.publish", "Manage content", "Content"),
    ("tenants.view", "View tenants", "System"),
    ("tenants.manage", "Manage tenants", "System"),
    ("tasks.view", "View background tasks", "Operations"),
    ("reports.view", "View reports", "Operations"),
]

ADMIN_ONLY_PERMISSIONS = {"roles.manage", "logs.view", "tenants.manage"}

CATALOG = {
    "General": ["Basic", "Standard"],
    "Premium": ["Pro", "Enterprise"],
}

SAMPLE_PRODUCTS = [
    ("Starter Plan", "SKU-001", Decimal("19.90"), "General", "Basic"),
    ("Pro Plan", "SKU-002", Decimal("49.90"), "Premium", "Pro"),
    ("Enterprise Plan", "SKU-003", Decimal("199.00"), "Premium", "Enterprise"),
]


async def seed(runtime) -> dict:
    """Idempotently create the schema, grouped permissions, users and sample data."""

    database = runtime.component("database")
    await database.create_all(Base.metadata)

    languages = runtime.component("language_service")
    await languages.seed_defaults()

    permission_service = runtime.component("permission_service")
    account_service = runtime.component("account_service")
    password_service = runtime.component("password_service")

    permission_ids = {}

    for code, label, group in PERMISSIONS:
        permission = await permission_service.create_permission(code, label, group=group)
        permission_ids[code] = permission.id

    admin_role = await permission_service.create_role("Administrator", tenant_id=0, description="Full access to every module.")
    await permission_service.set_role_permissions(admin_role.id, list(permission_ids.values()))

    staff_role = await permission_service.create_role("Staff", tenant_id=0, description="Access to every module except access control.")
    staff_permission_ids = [identifier for code, identifier in permission_ids.items() if code not in ADMIN_ONLY_PERMISSIONS]
    await permission_service.set_role_permissions(staff_role.id, staff_permission_ids)

    root = await account_service.create_user(
        tenant_id=0,
        identifiers=[("email", "root@fastkit.local")],
        display_name="Root",
        is_staff=True,
        is_root=True,
        password_hash=password_service.hash("root-password-123"),
    )
    await account_service.update_profile(root.id, timezone="America/Sao_Paulo")
    await permission_service.assign_role(root.id, admin_role.id, tenant_id=0)

    staff = await account_service.create_user(
        tenant_id=0,
        identifiers=[("email", "staff@fastkit.local")],
        display_name="Staff",
        is_staff=True,
        password_hash=password_service.hash("staff-password-123"),
    )
    await permission_service.assign_role(staff.id, staff_role.id, tenant_id=0)

    viewer_role = await permission_service.create_role("Viewer", tenant_id=0, description="Read-only access to the catalog.")
    await permission_service.set_role_permissions(viewer_role.id, [permission_ids["products.view"]])

    viewer = await account_service.create_user(
        tenant_id=0,
        identifiers=[("email", "viewer@fastkit.local")],
        display_name="Viewer",
        is_staff=True,
        password_hash=password_service.hash("viewer-password-123"),
    )
    await permission_service.assign_role(viewer.id, viewer_role.id, tenant_id=0)

    async with database.session_factory() as tenant_session:
        acme = Tenant(code="acme", name="Acme Inc.", default_locale="en", timezone="UTC")
        tenant_session.add(acme)
        tenant_session.add(Tenant(code="globex", name="Globex", status="suspended", default_locale="pt", timezone="America/Sao_Paulo"))
        await tenant_session.flush()
        acme_id = acme.id
        await tenant_session.commit()

    member = await account_service.create_user(
        tenant_id=acme_id,
        identifiers=[("email", "member@acme.com")],
        display_name="Acme Member",
        is_staff=True,
        password_hash=password_service.hash("member-password-123"),
    )
    await permission_service.assign_role(member.id, staff_role.id, tenant_id=acme_id)

    async with database.session_factory() as session:
        subcategory_ids = {}

        for category_name, subcategory_names in CATALOG.items():
            category = Category(name=category_name)
            session.add(category)
            await session.flush()

            for subcategory_name in subcategory_names:
                subcategory = Subcategory(name=subcategory_name, category_id=category.id)
                session.add(subcategory)
                await session.flush()
                subcategory_ids[(category_name, subcategory_name)] = (category.id, subcategory.id)

        for name, sku, price, category_name, subcategory_name in SAMPLE_PRODUCTS:
            category_id, subcategory_id = subcategory_ids[(category_name, subcategory_name)]
            session.add(Product(name=name, sku=sku, price=price, category_id=category_id, subcategory_id=subcategory_id))

        session.add(
            Showcase(
                title="Everything field showcase",
                summary="Demonstrates every admin field type.",
                body_html="<p>Rich <strong>text</strong> body.</p>",
                quantity=12,
                price=Decimal("99.90"),
                status="published",
                tags=["new", "featured"],
                brand_color="#4f46e5",
                is_featured=True,
                release_date=date(2026, 7, 14),
                release_time=time(9, 30),
                published_at=datetime(2026, 7, 14, 9, 30, tzinfo=timezone.utc),
                attributes={"weight": "1kg", "warranty": "2y"},
            )
        )

        moment = datetime(2026, 7, 15, 9, 0, tzinfo=timezone.utc)
        session.add(ScheduledTask(name="Nightly cleanup", task_name="demo.cleanup", schedule_type="cron", cron_expression="0 3 * * *", queue="default", next_run_at=moment))
        session.add(ScheduledTask(name="Hourly sync", task_name="demo.sync", schedule_type="interval", interval_seconds=3600, queue="default", next_run_at=moment, enabled=False))

        session.add(TaskExecution(task_name="demo.cleanup", queue="default", status="succeeded", available_at=moment, started_at=moment, finished_at=moment, attempt_count=1))
        session.add(TaskExecution(task_name="demo.sync", queue="default", status="running", available_at=moment, started_at=moment, attempt_count=1))
        session.add(TaskExecution(task_name="demo.export", queue="reports", status="failed", available_at=moment, attempt_count=3, error_message="upstream timeout"))

        session.add(ReportExecution(report_name="sales.summary", status="succeeded", progress=100, row_count=42, finished_at=moment))
        session.add(ReportExecution(report_name="tenant.usage", status="running", progress=40, row_count=0))

        await session.commit()

    return {"root": str(root.id), "staff": str(staff.id), "products": len(SAMPLE_PRODUCTS)}
