from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_files.models import (
    StorageFile,
    StorageFileReference,
    StorageFileVariant,
    UploadSession,
)
from fastkit_files.service import StorageFileService

MODELS = (StorageFile, StorageFileVariant, StorageFileReference, UploadSession)


class FilesApp(FastKitApp):
    name = "fastkit.files"
    label = "files"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db", "fastkit.storage")

    def register_models(self, context: BootstrapContext) -> None:
        for model in MODELS:
            context.models.register(model, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        database = context.component("database")
        storage = context.component("storage")

        context.set_component("file_service", StorageFileService(database, storage))
