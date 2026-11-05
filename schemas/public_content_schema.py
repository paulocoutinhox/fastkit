from datetime import date

from schemas.base_schema import BaseSchema


class PublicContentSchema(BaseSchema):
    """What a reader of a page gets: the page itself, and never the operator's free map, the keys it points with or who it belongs to."""

    uuid: str
    title: str
    tag: str
    content: str | None
    published_at: date | None
