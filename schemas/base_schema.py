from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    """The API speaks camelCase, and python speaks snake_case, so the alias is where the two meet."""

    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, validate_by_alias=True, from_attributes=True, extra="forbid", str_strip_whitespace=True)
