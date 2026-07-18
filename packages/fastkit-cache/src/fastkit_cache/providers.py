from fastkit_core.providers import ProviderRegistry
from fastkit_cache.database import DatabaseCacheProvider
from fastkit_cache.file import FileCacheProvider

cache_providers = ProviderRegistry("cache")


def build_file(settings, context):
    return FileCacheProvider(root=settings.cache.directory)


def build_database(settings, context):
    return DatabaseCacheProvider(context.component("database"))


cache_providers.register("file", build_file)
cache_providers.register("database", build_database)
