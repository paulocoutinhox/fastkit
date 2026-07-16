from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_assets.models import Asset, AssetAttachment, AssetVariant, UploadSession
from fastkit_assets.service import AssetService

MODELS = (Asset, AssetVariant, AssetAttachment, UploadSession)


class AssetsApp(FastKitApp):
    name = "fastkit.assets"
    label = "assets"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db", "fastkit.storage")

    def register_models(self, context: BootstrapContext) -> None:
        for model in MODELS:
            context.models.register(model, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        database = context.component("database")
        storage = context.component("storage")

        context.set_component("asset_service", AssetService(database.session_factory, storage))
