from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_admin.api import build_admin_router
from fastkit_admin.pages import build_admin_pages_router, build_page_config
from fastkit_admin.profile import build_profile_router
from fastkit_admin.rendering import AdminRenderer
from fastkit_admin.security import build_admin_deps
from fastkit_admin.uploads import build_upload_router
from fastkit_content.routers import build_content_router
from fastkit_permissions.routers import build_role_router
from app.admin import ADMIN_RESOURCES
from app.auth_routes import build_auth_router
from app.gdpr import build_gdpr_router
from app.models import Category, Product, Showcase, Subcategory
from app.reports import build_report_router, setup_reports
from app.tasks import setup_tasks
from app.translations import DEMO_PT
from app.uploads import build_avatar_upload_handler, build_file_upload_handler, build_image_upload_handler

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _read_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


MENU_GROUPS = [
    ("catalog", "Catalog", 0, "package"),
    ("content", "Content", 1, "file-text"),
    ("operations", "Operations", 2, "clock-play"),
    ("reports", "Reports", 3, "report-analytics"),
    ("system", "System", 4, "building"),
    ("internal", "Internal", 5, "shield-lock"),
]

MENU_ITEMS = [
    ("Products", "catalog", "products"),
    ("Categories", "catalog", "categories"),
    ("Subcategories", "catalog", "subcategories"),
    ("Field showcase", "content", "showcase"),
    ("Geo samples", "catalog", "geo-samples"),
    ("Content", "content", "content"),
    ("Languages", "content", "languages"),
    ("Scheduled tasks", "operations", "scheduled-tasks"),
    ("Task runs", "operations", "task-runs"),
    ("Report runs", "operations", "report-runs"),
    ("Tenants", "system", "tenants"),
    ("Users", "system", "users"),
    ("Roles", "system", "roles"),
    ("Activity log", "internal", "activity"),
]


class DemoApp(FastKitApp):
    name = "demo"
    label = "demo"
    version = "1.0.0"
    requires = (
        "fastkit.core",
        "fastkit.db",
        "fastkit.accounts",
        "fastkit.auth",
        "fastkit.permissions",
        "fastkit.admin",
        "fastkit.i18n",
        "fastkit.logging",
        "fastkit.storage",
        "fastkit.assets",
        "fastkit.content",
        "fastkit.tenancy",
        "fastkit.tasks",
        "fastkit.reports",
    )

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(Category, source=self.name)
        context.models.register(Subcategory, source=self.name)
        context.models.register(Product, source=self.name)
        context.models.register(Showcase, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        setup_tasks(context.component("task_registry"))

    def register_translations(self, context: BootstrapContext) -> None:
        context.component("translator").add_catalog("pt", DEMO_PT)

    def register_admin(self, context: BootstrapContext) -> None:
        site = context.component("admin_site")
        storage = context.component("storage")
        task_queue = context.component("task_queue")
        base_url = context.settings.storage.base_url

        for resource in ADMIN_RESOURCES:
            instance = resource()
            instance.storage = storage
            instance.media_base_url = base_url

            if hasattr(instance, "task_queue"):
                instance.task_queue = task_queue

            site.register(instance)

        for key, label, order, icon in MENU_GROUPS:
            site.add_group(key, label, order=order, icon=icon)

        for label, group, resource in MENU_ITEMS:
            site.add_menu(label, group=group, resource=resource)

        report_registry = context.component("report_registry")
        setup_reports(report_registry, context.component("report_service"))

        for name in report_registry.names():
            definition = report_registry.get(name)
            site.add_menu(definition.title, group="reports", path=f"{context.settings.admin.path}/reports/{name}", permission="reports.view", icon="report-analytics")

    def register_routers(self, context: BootstrapContext) -> None:
        runtime = context.runtime
        settings = context.settings
        site = context.component("admin_site")
        account_service = context.component("account_service")
        password_service = context.component("password_service")
        secure_cookie = settings.app.environment in ("stage", "prod")

        audit_service = runtime.component("audit_log_service")

        async def audit(action, resource_type, resource_id):
            await audit_service.record(action=action, resource_type=resource_type, resource_id=resource_id)

        deps, security = build_admin_deps(runtime, audit=audit)
        image_handler = build_image_upload_handler(runtime, settings.storage.base_url)
        avatar_handler = build_avatar_upload_handler(runtime, settings.storage.base_url)
        file_handler = build_file_upload_handler(runtime, settings.storage.base_url)
        asset_service = runtime.component("asset_service")

        async def resolve_avatar_url(asset_id):
            asset = await asset_service.get(asset_id)

            return f"{settings.storage.base_url}/{asset.object_key}" if asset else None

        api_path = settings.admin.api_path
        context.routers.include(build_auth_router(runtime, security, secure_cookie), prefix=api_path, source=self.name)
        context.routers.include(build_gdpr_router(runtime, security), prefix=api_path, source=self.name)
        context.routers.include(build_role_router(runtime, security), prefix=api_path, source=self.name)
        context.routers.include(build_content_router(runtime, security), prefix=api_path, source=self.name)
        context.routers.include(build_report_router(runtime, security), prefix=api_path, source=self.name)
        context.routers.include(build_profile_router(deps, account_service, password_service, upload_avatar=avatar_handler, avatar_url=resolve_avatar_url), prefix=api_path, source=self.name)
        context.routers.include(build_upload_router(deps, {"image": image_handler, "file": file_handler}), prefix=api_path, source=self.name)
        context.routers.include(build_admin_router(site, deps), prefix=api_path, source=self.name)

        report_service = runtime.component("report_service")
        report_registry = runtime.component("report_registry")

        async def report_data(name, session, locale, params):
            schema = report_registry.get(name).to_schema()
            result = await report_service.build_result(name, session, dict(params))

            return {"title": schema["title"], "columns": schema["columns"], "filters": schema["filters"], "rows": result.rows, "formats": report_service.export_formats()}

        async def profile_data(user, locale):
            identifiers = await account_service.list_identifiers(user.id)
            asset_id = user.profile.avatar_asset_id if getattr(user, "profile", None) else None
            url = await resolve_avatar_url(asset_id) if asset_id else None

            return {
                "display_name": user.display_name,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "avatar_url": url,
                "identifier_types": account_service.identifier_types(),
                "identifiers": [{"id": str(item.id), "type": item.type, "value": item.value} for item in identifiers],
            }

        renderer = AdminRenderer(override_dirs=[str(TEMPLATES_DIR)])
        page_config = build_page_config(settings.admin, theme={"brand_name": "FastKit"}, recaptcha=settings.auth.recaptcha)
        context.routers.include(build_admin_pages_router(renderer, site, deps, page_config, avatar_url=resolve_avatar_url, report_data=report_data, profile_data=profile_data), source=self.name)
        context.routers.include(self._build_home_router(), source=self.name)

    def _build_home_router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/", response_class=HTMLResponse)
        async def home():
            return _read_template("index.html")

        return router
