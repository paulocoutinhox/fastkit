from pathlib import Path

from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_mail.models import EmailDelivery
from fastkit_mail.providers import mail_providers
from fastkit_mail.service import MailService
from fastkit_mail.templates import MailTemplateRenderer

PACKAGE_TEMPLATES = str(Path(__file__).parent / "templates")


def build_provider(settings):
    return mail_providers.build(settings.mail.provider, settings)


def build_renderer(project_dirs: list[str]) -> MailTemplateRenderer:
    return MailTemplateRenderer(search_dirs=[*project_dirs, PACKAGE_TEMPLATES])


class MailApp(FastKitApp):
    name = "fastkit.mail"
    label = "mail"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(EmailDelivery, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        settings = context.settings
        database = context.component("database")

        project_dirs = [directory.path for directory in context.templates.directories()]
        renderer = build_renderer(project_dirs)
        provider = build_provider(settings)

        context.set_component("mail_renderer", renderer)
        context.set_component("mail_provider", provider)
        context.set_component(
            "mail_service",
            MailService(
                database,
                renderer,
                provider,
                settings.mail.provider,
                settings.mail.default_from,
            ),
        )
