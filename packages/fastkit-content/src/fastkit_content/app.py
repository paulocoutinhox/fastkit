from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_content.models import Content, ContentTranslation, Language
from fastkit_content.service import ContentService, LanguageService


class ContentApp(FastKitApp):
    name = "fastkit.content"
    label = "content"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db", "fastkit.i18n")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(Language, source=self.name)
        context.models.register(Content, source=self.name)
        context.models.register(ContentTranslation, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        database = context.component("database")

        context.set_component("language_service", LanguageService(database))
        context.set_component("content_service", ContentService(database))
