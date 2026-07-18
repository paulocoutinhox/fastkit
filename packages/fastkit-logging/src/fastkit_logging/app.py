from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_logging.config import setup_logging
from fastkit_logging.models import AuditLog, SystemLog
from fastkit_logging.service import AuditLogService, SystemLogService


class LoggingApp(FastKitApp):
    name = "fastkit.logging"
    label = "logging"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(SystemLog, source=self.name)
        context.models.register(AuditLog, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        settings = context.settings
        setup_logging(
            level=settings.logging.level,
            file_path=settings.logging.file,
            environment=settings.app.environment,
        )

        database = context.component("database")

        context.set_component(
            "system_log_service", SystemLogService(database, settings.app.environment)
        )
        context.set_component("audit_log_service", AuditLogService(database))
