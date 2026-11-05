from pydantic import Field

from schemas.base_schema import BaseSchema


class BannerCountRequest(BaseSchema):
    """Who is being counted, which a browser carries in a cookie and an application carries here."""

    visitor: str | None = Field(None, max_length=512)
