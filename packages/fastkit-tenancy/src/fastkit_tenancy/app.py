from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_tenancy.models import Tenant
from fastkit_tenancy.service import TenantService


class TenancyApp(FastKitApp):
    name = "fastkit.tenancy"
    label = "tenancy"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(Tenant, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        database = context.component("database")
        context.set_component("tenant_service", TenantService(database.session_factory))
