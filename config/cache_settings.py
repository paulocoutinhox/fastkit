from pydantic import BaseModel


class CacheSettings(BaseModel):
    """What an assembled answer is kept in, which a machine somebody develops on leaves off so a page shows what was just edited."""

    enabled: bool = False

    # Nothing evicts anything here, so each of these is also how long an edit in the panel takes to reach a reader.
    home_ttl: int = 60
    banners_ttl: int = 60
    products_ttl: int = 120
    search_ttl: int = 30
    plans_ttl: int = 300
    content_ttl: int = 300
    gallery_ttl: int = 300
