"""The ids in the order they should stand, which is the whole instruction."""

from pydantic import Field, field_validator

from helpers.i18n import translate
from schemas.base_schema import BaseSchema
from schemas.common import Reference


class ReorderRequest(BaseSchema):
    ids: list[Reference] = Field(min_length=1, max_length=200)

    @field_validator("ids")
    @classmethod
    def each_once(cls, ids: list[int]) -> list[int]:
        """An order names every row once, and a row named twice stands in two places."""
        if len(set(ids)) != len(ids):
            raise ValueError(translate("validation.repeated"))

        return ids
