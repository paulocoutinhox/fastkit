from fastkit_core.providers import ProviderRegistry
from fastkit_storage.local import LocalStorageProvider

storage_providers = ProviderRegistry("storage")


def build_local(settings):
    return LocalStorageProvider(root=settings.storage.root, base_url=settings.storage.base_url, secret=settings.app.secret_key)


def build_s3(settings):
    import aioboto3

    from fastkit_storage.s3 import S3StorageProvider

    session = aioboto3.Session()

    return S3StorageProvider(session.client("s3"), bucket=settings.storage.root)


storage_providers.register("local", build_local)
storage_providers.register("s3", build_s3)
