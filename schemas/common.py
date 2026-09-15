import json
import re
from copy import copy
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import available_timezones

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, create_model
from pydantic.alias_generators import to_camel

from helpers.dates import as_utc
from helpers.i18n import translate
from helpers.text import is_valid_cpf, only_digits
from models.base import BIG_INTEGER_MAX, INTEGER_MAX, JSON_DEPTH_MAX, Money

# A text column holds 65535 bytes and a character can cost four of them, so this is what always fits.
FREE_TEXT_MAX = 16_000

# A number arrives punctuated the way its country writes it and is stored as the number, so the shape and the number are bounded apart.
WRITTEN_PHONE_MAX = 32
PHONE_MAX = 16

# The zone database is read off the disk and never moves while this process lives, so it is read once instead of on every field it answers for.
TIMEZONES = sorted(available_timezones())


def valid_document(value: str | None) -> str | None:
    if not value:
        return None

    if not is_valid_cpf(value):
        raise ValueError(translate("validation.invalid-document"))

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


def on_the_calendar(value: datetime | None) -> datetime | None:
    """A moment is stored in UTC, and one written in an offset that carries it past the last or the first day there is fails where it is converted."""
    try:
        return as_utc(value)
    except OverflowError as error:
        raise ValueError(translate("validation.invalid-instant")) from error


def a_uuid(value: str) -> str:
    """The canonical form of a uuid a client drew, so the same one written in capitals is not a second event."""
    try:
        return str(UUID(value))
    except ValueError:
        raise ValueError(translate("validation.invalid-format")) from None


def nesting(value) -> int:
    """How many levels a document nests, counted without recursion so a hostile one never reaches the interpreter's own limit."""
    deepest = 0
    pending = [(value, 1)]

    while pending:
        current, level = pending.pop()

        if isinstance(current, dict | list):
            deepest = max(deepest, level)
            pending.extend((child, level + 1) for child in (current.values() if isinstance(current, dict) else current))

    return deepest


def stored_as_json(value: dict) -> dict:
    """A map is stored as JSON, which holds no NaN and no infinity, and MySQL refuses the text that would carry one or that nests past its depth."""
    try:
        json.dumps(value, allow_nan=False)
    except ValueError as error:
        raise ValueError(translate("validation.finite-numbers")) from error

    # A map past the depth is written by SQLite and then answers every listing that reads it with a five hundred, so it is refused where it arrives.
    if nesting(value) > JSON_DEPTH_MAX:
        raise ValueError(translate("validation.too-deep"))

    return value


def a_host(value):
    """A host is matched against what a browser sends, which is lowercase and never carries the dot that closes a name."""
    return value.strip().lower().rstrip(".") if isinstance(value, str) else value


def an_address(value: str) -> str:
    """An address the gateway reaches is one a parser reads down to its host, and a bracket left open matches the pattern and is no address."""
    try:
        parts = urlsplit(value)
        reachable = parts.hostname is not None and (parts.port is None or parts.port > 0)
    except ValueError:
        reachable = False

    if not reachable:
        raise ValueError(translate("validation.invalid-format"))

    return value


def written_as_an_identity(value: str | None) -> str | None:
    if value and not IDENTITY.fullmatch(value):
        raise ValueError(translate("validation.invalid-username"))

    return value


# What an identity is written with, which leaves out everything that would forge a line of the record it is written into.
# A username carries a letter, which is what keeps it from ever being read as a document or a phone number at sign in.
IDENTITY = re.compile(r"(?=[^A-Za-z]*[A-Za-z])[A-Za-z0-9._-]+")

# Where a link points, which is another site or a page of this one, and never a scheme a browser runs.
LinkUrl = Annotated[str | None, Field(None, max_length=512, pattern=r"^(https?://\S+|/|/[^/\\\s]\S*)$")]

# The host a brand answers on, written the way a request names it, because SQLite compares it as typed and MySQL does not, and a port or a scheme is never part of a host.
Domain = Annotated[str, BeforeValidator(a_host), Field(min_length=1, max_length=253, pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$")]

# Where a gateway sends a buyer back, which an application names and only it knows, and which has to be absolute for the gateway to reach it.
ReturnUrl = Annotated[str, Field(max_length=2048, pattern=r"^https?://\S+$"), AfterValidator(an_address)]

# A number is bounded at both ends, because one past what its column holds overflows inside the driver instead of being refused — and MySQL is where that column is narrow, not SQLite.
Position = Annotated[int, Field(0, ge=0, le=INTEGER_MAX)]
IntervalValue = Annotated[int | None, Field(None, ge=1, le=INTEGER_MAX)]
Quantity = Annotated[int, Field(1, ge=0, le=BIG_INTEGER_MAX)]

# What a client names a row by, bounded because a number past what the column holds overflows inside the driver before any lookup gets to refuse it.
Reference = Annotated[int, Field(ge=1, le=BIG_INTEGER_MAX)]
OptionalReference = Annotated[int | None, Field(None, ge=1, le=BIG_INTEGER_MAX)]

# A movement is the one number that carries a sign, because an adjustment is what exists to move a balance either way.
Amount = Annotated[int, Field(ge=-BIG_INTEGER_MAX, le=BIG_INTEGER_MAX)]

# A key a client draws to name what it reports, unique across every account, so a counter a device numbers from one would collide with every other.
ClientUuid = Annotated[str, Field(max_length=36), AfterValidator(a_uuid)]

# A price is what a money column holds, read off the column: MySQL refuses a larger one as a 500 and rounds a finer one that SQLite keeps as written.
Price = Annotated[Decimal, Field(ge=0, max_digits=Money.precision, decimal_places=Money.scale)]


# A column the table says must be there is a column a blank never fills, and a name of spaces draws a page with nothing on it.
def Text(limit: int):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=limit)]


# The rules of an identity are the same wherever it is written, so a schema declares the type and never the check.
Username = Annotated[str | None, Field(None, min_length=3, max_length=64), AfterValidator(written_as_an_identity)]
Document = Annotated[str | None, Field(None, max_length=14), AfterValidator(valid_document)]
MobilePhone = Annotated[str | None, Field(None, max_length=WRITTEN_PHONE_MAX), AfterValidator(dialled)]
Timezone = Annotated[str, Field("UTC", max_length=64), AfterValidator(known_timezone)]
Instant = Annotated[datetime, AfterValidator(on_the_calendar)]

# A login is any of the four identities, and a password that is being set is held to the length a new one needs.
Login = Annotated[str, Field(min_length=3, max_length=255)]
NewPassword = Annotated[str, Field(min_length=8, max_length=128)]

# The answer is a word read off an image or a token Google minted, which runs to a couple of thousand characters, and the token is the signed challenge this side issued.
CaptchaAnswer = Annotated[str | None, Field(None, max_length=4096)]
CaptchaToken = Annotated[str | None, Field(None, max_length=1024)]
JsonMap = Annotated[dict, AfterValidator(stored_as_json)]


class BaseSchema(BaseModel):
    """The API speaks camelCase, and python speaks snake_case, so the alias is where the two meet."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True, extra="forbid", str_strip_whitespace=True)


class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime


def as_optional(name: str, base: type[BaseModel]) -> type[BaseModel]:
    """The edit payload of a resource is its create payload with every field allowed to be left out, keeping the same validation rules."""
    fields = {}

    for field_name, info in base.model_fields.items():
        clone = copy(info)
        clone.default = None
        clone.default_factory = None

        # The annotation is kept, so what may be left out is every field and what may be written as nothing is only what the column lets be nothing.
        # Widening it to Optional let a null through to a column the table declares a value for, and the database calls that a duplicated record.
        fields[field_name] = (info.annotation, clone)

    return create_model(name, __base__=base, **fields)
