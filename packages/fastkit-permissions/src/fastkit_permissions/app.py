from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_core.store import MemoryKeyValueStore, SharedKeyValueStore
from fastkit_permissions.authorization import Authorizer
from fastkit_permissions.cache import PermissionCache
from fastkit_permissions.models import Permission, Role, RolePermission, UserRole
from fastkit_permissions.service import PermissionService

MODELS = (Permission, Role, RolePermission, UserRole)


def build_store(settings, context: BootstrapContext):
    kind = settings.permissions.store

    if kind == "memory":
        return MemoryKeyValueStore()

    if kind == "shared":
        return SharedKeyValueStore(lambda: context.component("cache_provider"))

    raise ValueError(f"unknown permissions store '{kind}'")


class PermissionsApp(FastKitApp):
    name = "fastkit.permissions"
    label = "permissions"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db", "fastkit.accounts")

    def register_models(self, context: BootstrapContext) -> None:
        for model in MODELS:
            context.models.register(model, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        database = context.component("database")
        cache = PermissionCache(build_store(context.settings, context))
        service = PermissionService(database, cache)

        context.set_component("permission_cache", cache)
        context.set_component("permission_service", service)
        context.set_component("authorizer", Authorizer(service, cache))
