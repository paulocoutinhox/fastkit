from pydantic import Field

from schemas.app_event_input import AppEventInput
from schemas.base_schema import BaseSchema


class AppEventBatchRequest(BaseSchema):
    events: list[AppEventInput] = Field(min_length=1, max_length=100)
