from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_admin.messages import ADMIN_MESSAGES
from fastkit_admin.site import AdminSite


class AdminApp(FastKitApp):
    name = "fastkit.admin"
    label = "admin"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.auth", "fastkit.permissions", "fastkit.i18n")

    def register_services(self, context: BootstrapContext) -> None:
        admin = context.settings.admin
        site = AdminSite(name="main", title="Administration", path=admin.path, api_path=admin.api_path)

        context.set_component("admin_site", site)

    def register_translations(self, context: BootstrapContext) -> None:
        translator = context.component("translator")

        for locale, messages in ADMIN_MESSAGES.items():
            translator.add_catalog(locale, messages)
