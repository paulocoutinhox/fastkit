from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import ClientUuid, Instant, JsonMap


class AppEventInput(BaseSchema):
    uuid: ClientUuid
    name: str = Field(max_length=128)
    params: JsonMap = Field(default_factory=dict)
    occurred_at: Instant
