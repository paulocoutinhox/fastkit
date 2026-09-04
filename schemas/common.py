import re
from copy import copy
from datetime import datetime
from typing import Annotated, Optional
from zoneinfo import available_timezones

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, create_model
from pydantic.alias_generators import to_camel

from helpers.i18n import translate
from helpers.text import is_valid_cpf, only_digits
from models.base import BIG_INTEGER_MAX, INTEGER_MAX

# A text column holds 65535 bytes and a character can cost four of them, so this is what always fits.
FREE_TEXT_MAX = 16_000

# A number arrives punctuated the way its country writes it and is stored as the number, so the shape and the number are bounded apart.
WRITTEN_PHONE_MAX = 32
PHONE_MAX = 16

# The zone database is read off the disk and never moves while this process lives, so it is read once instead of on every field it answers for.
TIMEZONES = sorted(available_timezones())


def valid_cpf(value: str | None) -> str | None:
    if not value:
        return None

    if not is_valid_cpf(value):
        raise ValueError(translate("validation.invalid-cpf"))

    return only_digits(value)


def dialled(value: str | None) -> str | None:
    """A number is written the way its country writes it, and what is stored is the number rather than the shape it was written in."""
    digits = only_digits(value)

    if len(digits) > PHONE_MAX:
        raise ValueError(translate("validation.string-too-long", max_length=PHONE_MAX))

    return digits or None


def known_timezone(value: str | None) -> str | None:
    if value and value not in TIMEZONES:
        raise ValueError(translate("validation.invalid-timezone"))

    return value


def written_as_an_identity(value: str | None) -> str | None:
    if value and not IDENTITY.fullmatch(value):
        raise ValueError(translate("validation.invalid-username"))

    return value


# What an identity is written with, which leaves out everything that would forge a line of the record it is written into.
IDENTITY = re.compile(r"[A-Za-z0-9._-]+")

# Where a link points, which is another site or a page of this one, and never a scheme a browser runs.
LinkUrl = Annotated[str | None, Field(None, max_length=512, pattern=r"^(https?://\S+|/|/[^/\\\s]\S*)$")]

# Where a gateway sends a buyer back, which an application names and only it knows, and which has to be absolute for the gateway to reach it.
ReturnUrl = Annotated[str, Field(max_length=2048, pattern=r"^https?://\S+$")]

# A number is bounded at both ends, because one past what its column holds overflows inside the driver instead of being refused — and MySQL is where that column is narrow, not SQLite.
Position = Annotated[int, Field(0, ge=0, le=INTEGER_MAX)]
IntervalValue = Annotated[int | None, Field(None, ge=1, le=INTEGER_MAX)]
Quantity = Annotated[int, Field(1, ge=0, le=BIG_INTEGER_MAX)]

# What a client names a row by, bounded because a number past what the column holds overflows inside the driver before any lookup gets to refuse it.
Reference = Annotated[int, Field(ge=1, le=BIG_INTEGER_MAX)]
OptionalReference = Annotated[int | None, Field(None, ge=1, le=BIG_INTEGER_MAX)]

# A movement is the one number that carries a sign, because an adjustment is what exists to move a balance either way.
Amount = Annotated[int, Field(ge=-BIG_INTEGER_MAX, le=BIG_INTEGER_MAX)]


# A column the table says must be there is a column a blank never fills, and a name of spaces draws a page with nothing on it.
def Text(limit: int):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=limit)]


# The rules of an identity are the same wherever it is written, so a schema declares the type and never the check.
Username = Annotated[str | None, Field(None, min_length=3, max_length=64), AfterValidator(written_as_an_identity)]
Cpf = Annotated[str | None, Field(None, max_length=14), AfterValidator(valid_cpf)]
MobilePhone = Annotated[str | None, Field(None, max_length=WRITTEN_PHONE_MAX), AfterValidator(dialled)]
Timezone = Annotated[str, Field("UTC", max_length=64), AfterValidator(known_timezone)]
OptionalTimezone = Annotated[str | None, Field(None, max_length=64), AfterValidator(known_timezone)]


class BaseSchema(BaseModel):
    """The API speaks camelCase, and python speaks snake_case, so the alias is where the two meet."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid", str_strip_whitespace=True)


class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime


def as_optional(name: str, base: type[BaseModel]) -> type[BaseModel]:
    """The edit payload of a resource is its create payload with every field optional, keeping the same validation rules."""
    fields = {}

    for field_name, info in base.model_fields.items():
        clone = copy(info)
        clone.default = None
        clone.default_factory = None
        fields[field_name] = (Optional[info.annotation], clone)

    return create_model(name, __base__=base, **fields)
