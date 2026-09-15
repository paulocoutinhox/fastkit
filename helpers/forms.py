"""A form of the site, read back through the same schemas the API validates with."""

from pydantic import BaseModel
from pydantic import ValidationError as SchemaError
from starlette.datastructures import FormData

from helpers.errors import validation_message


def payload_of(form: FormData, names: tuple[str, ...]) -> dict:
    """A form sends every field it draws, and an empty one is a value nobody typed rather than an empty string."""
    return {name: form.get(name).strip() or None for name in names if isinstance(form.get(name), str)}


def drawn_as(location: tuple) -> str:
    """A page marks the field by the name it drew the input with, and the camelCase one is what the API answers instead."""
    return str(location[0]) if location else ""


def validated(model: type[BaseModel], payload: dict) -> tuple[BaseModel | None, dict[str, str]]:
    """The same rules the API answers by, read back as a map the page can mark a field with."""
    try:
        return model.model_validate(payload), {}
    except SchemaError as refused:
        return None, {drawn_as(error["loc"]): validation_message(error) for error in refused.errors()}
