from datetime import datetime

from schemas.base_schema import BaseSchema


class AccountProductSchema(BaseSchema):
    """What the account owns, where the address of the file is only ever built for somebody who owns it."""

    id: int
    uuid: str
    name: str
    slug: str
    description: str | None
    image_url: str | None
    file_url: str | None
    granted_at: datetime
