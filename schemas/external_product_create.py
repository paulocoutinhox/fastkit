from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import FREE_TEXT_MAX, JsonMap, Price, Reference, Text


class ExternalProductCreate(BaseSchema):
    integration_id: Reference
    plan_id: Reference
    external_id: Text(191)
    display_name: str | None = Field(None, max_length=255)
    reference_currency: str | None = Field(None, max_length=3)
    reference_price: Price | None = None
    notes: str | None = Field(None, max_length=FREE_TEXT_MAX)
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
