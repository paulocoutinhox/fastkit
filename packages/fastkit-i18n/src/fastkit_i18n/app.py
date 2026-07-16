from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_i18n.catalogs import BASE_CATALOGS
from fastkit_i18n.resolver import LocaleResolver
from fastkit_i18n.translator import Translator


class I18nApp(FastKitApp):
    name = "fastkit.i18n"
    label = "i18n"
    version = "1.0.0"
    requires = ("fastkit.core",)

    def register_services(self, context: BootstrapContext) -> None:
        settings = context.settings.i18n

        translator = Translator(BASE_CATALOGS, supported=settings.supported_locales, default_locale=settings.default_locale)
        resolver = LocaleResolver(supported=translator.supported, default_locale=settings.default_locale)

        context.set_component("translator", translator)
        context.set_component("locale_resolver", resolver)
