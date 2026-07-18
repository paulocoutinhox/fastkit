from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_reports.contracts import ReportRegistry
from fastkit_reports.models import ReportExecution
from fastkit_reports.renderers import default_renderers
from fastkit_reports.service import ReportService


class ReportsApp(FastKitApp):
    name = "fastkit.reports"
    label = "reports"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(ReportExecution, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        database = context.component("database")
        registry = ReportRegistry()

        context.set_component("report_registry", registry)
        context.set_component(
            "report_service", ReportService(database, registry, default_renderers())
        )
