from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_accounts.models import LoginIdentifier, User, UserProfile
from fastkit_accounts.normalizers import default_registry
from fastkit_accounts.service import AccountService


class AccountsApp(FastKitApp):
    name = "fastkit.accounts"
    label = "accounts"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db", "fastkit.tenancy")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(User, source=self.name)
        context.models.register(UserProfile, source=self.name)
        context.models.register(LoginIdentifier, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        database = context.component("database")
        normalizers = default_registry()

        context.set_component("normalizer_registry", normalizers)
        context.set_component("account_service", AccountService(database.session_factory, normalizers))
