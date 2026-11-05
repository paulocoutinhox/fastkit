from pydantic import computed_field

from helpers.text import display_name
from schemas.base_schema import BaseSchema


class NamedAccount(BaseSchema):
    """The one name a screen calls an account by, computed the same way wherever an account is answered."""

    @computed_field
    @property
    def display_name(self) -> str:
        return display_name(self)
