"""How a listing is asked for and answered, with a ceiling nobody can raise."""

from typing import Annotated

from fastapi import Depends, Query

from helpers.page_params import PageParams
from models.base import BIG_INTEGER_MAX

PAGE_SIZE = 50


MAX_PAGE_SIZE = 200


# What every listing takes, declared once: a listing a client reads by hand answers the same two ceilings the factory does, and an offset past what a column holds overflows inside the driver.
ListingLimit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]


ListingOffset = Annotated[int, Query(ge=0, le=BIG_INTEGER_MAX)]


def get_page_params(limit: ListingLimit = PAGE_SIZE, offset: ListingOffset = 0, search: str | None = Query(None, max_length=128), ordering: str | None = Query(None, max_length=64)) -> PageParams:
    return PageParams(limit=limit, offset=offset, search=search, ordering=ordering)


CurrentPage = Annotated[PageParams, Depends(get_page_params)]
