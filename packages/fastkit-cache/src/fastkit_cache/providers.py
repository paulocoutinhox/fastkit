from fastkit_core.providers import ProviderRegistry
from fastkit_cache.database import DatabaseCacheProvider
from fastkit_cache.file import FileCacheProvider

cache_providers = ProviderRegistry("cache")


def build_file(settings, context):
    return FileCacheProvider(root=settings.cache.directory)


def build_database(settings, context):
    return DatabaseCacheProvider(context.component("database").session_factory)


def build_redis(settings, context):
    from redis.asyncio import Redis

    from fastkit_cache.redis import RedisCacheProvider

    return RedisCacheProvider(Redis.from_url(settings.cache.redis_url))


cache_providers.register("file", build_file)
cache_providers.register("database", build_database)
cache_providers.register("redis", build_redis)
