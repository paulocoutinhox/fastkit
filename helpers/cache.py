"""The assembled answer a surface already gave, kept under the key that names it until that name goes stale."""

import hashlib
import json
from datetime import timedelta

from cachefy.app import Cachefy
from cachefy.store.sqlalchemy import SqlAlchemyStore

from helpers.db import async_engine
from helpers.settings import settings

store = SqlAlchemyStore(async_engine)
app = Cachefy(store)

home = app.space("home", ttl=timedelta(seconds=settings.cache.home_ttl))
banners = app.space("banners", ttl=timedelta(seconds=settings.cache.banners_ttl))
products = app.space("products", ttl=timedelta(seconds=settings.cache.products_ttl))
search = app.space("search", ttl=timedelta(seconds=settings.cache.search_ttl))
plans = app.space("plans", ttl=timedelta(seconds=settings.cache.plans_ttl))
content = app.space("content", ttl=timedelta(seconds=settings.cache.content_ttl))
gallery = app.space("gallery", ttl=timedelta(seconds=settings.cache.gallery_ttl))


def every():
    """Every space this application keeps, read from the library so a second list of them can never drift."""
    return tuple(app.spaces.values())


def named(**parts) -> str:
    """One part left out is one tenant reading the page of another, and a tag is as long as its column, so the parts are digested into a width the key column holds."""
    described = json.dumps(sorted((name, value) for name, value in parts.items() if value is not None), separators=(",", ":"), default=str)

    return hashlib.sha256(described.encode()).hexdigest()


async def answered(space, key: str, produce):
    if not settings.cache.enabled:
        return await produce()

    return await space.fetch(key, produce)
