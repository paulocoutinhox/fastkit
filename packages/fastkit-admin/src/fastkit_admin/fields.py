import json
import re
from datetime import date, datetime, time
from decimal import Decimal

from fastkit_core.errors.codes import VALIDATION_FAILED
from fastkit_core.errors.exceptions import FieldError, ValidationError
from fastkit_core.sanitize import sanitize_html
from fastkit_admin.formatters import (
    DecimalParseError,
    format_date,
    format_datetime,
    format_decimal,
    format_time,
    parse_date,
    parse_datetime,
    parse_decimal,
    parse_time,
)


class AdminField:
    """Base admin field describing how a value is edited, displayed and parsed."""

    field_type = "text"

    def __init__(self, name: str, label: str | None = None, required: bool = False, readonly: bool = False, help_text: str | None = None, placeholder: str | None = None, default=None, write_only: bool = False, virtual: bool = False, hide_label: bool = False):
        self.name = name
        self.label = label or name.replace("_", " ").title()
        self.required = required
        self.readonly = readonly
        self.help_text = help_text
        self.placeholder = placeholder
        self.default = default
        self.write_only = write_only
        self.virtual = virtual
        self.hide_label = hide_label

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "type": self.field_type,
            "label": self.label,
            "required": self.required,
            "readonly": self.readonly,
            "help_text": self.help_text,
            "placeholder": self.placeholder,
            "default": self.default,
            "virtual": self.virtual,
            "hide_label": self.hide_label,
        }

    def format_value(self, value, locale: str = "en"):
        return value

    def parse_value(self, raw, locale: str = "en"):
        return raw

    def _fail(self, code: str) -> ValidationError:
        return ValidationError(VALIDATION_FAILED, field_errors=[FieldError(self.name, code)])

    def validate(self, value) -> None:
        if self.required and (value is None or value == ""):
            raise self._fail("validation.required")


class TextField(AdminField):
    field_type = "text"

    def __init__(self, *args, max_length: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_length = max_length

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["max_length"] = self.max_length

        return schema

    def validate(self, value) -> None:
        super().validate(value)

        if value is not None and self.max_length is not None and len(str(value)) > self.max_length:
            raise self._fail("validation.string-max-length")


class TextareaField(TextField):
    field_type = "textarea"


class EmailField(TextField):
    field_type = "email"

    def validate(self, value) -> None:
        super().validate(value)

        if value not in (None, "") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value)):
            raise self._fail("validation.email-invalid")


class URLField(TextField):
    field_type = "url"

    def validate(self, value) -> None:
        super().validate(value)

        if value not in (None, "") and not re.fullmatch(r"https?://[^\s]+", str(value)):
            raise self._fail("validation.url-invalid")


class MaskedField(TextField):
    field_type = "masked"

    def __init__(self, *args, mask: str, pattern: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mask = mask
        self.pattern = pattern

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["mask"] = self.mask
        schema["pattern"] = self.pattern

        return schema

    def validate(self, value) -> None:
        super().validate(value)

        if value not in (None, "") and self.pattern is not None and not re.fullmatch(self.pattern, str(value)):
            raise self._fail("validation.pattern-invalid")


class PasswordField(AdminField):
    field_type = "password"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("write_only", True)
        super().__init__(*args, **kwargs)


class BooleanField(AdminField):
    field_type = "boolean"

    def format_value(self, value, locale: str = "en"):
        return bool(value)

    def parse_value(self, raw, locale: str = "en"):
        if isinstance(raw, bool):
            return raw

        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    def validate(self, value) -> None:
        pass


class NumberField(AdminField):
    field_type = "number"

    def parse_value(self, raw, locale: str = "en"):
        if raw is None or raw == "":
            return None

        try:
            return int(raw)
        except (TypeError, ValueError) as error:
            raise self._fail("validation.integer-invalid") from error


class DecimalField(AdminField):
    field_type = "decimal"

    def __init__(self, *args, decimal_places: int = 2, **kwargs):
        super().__init__(*args, **kwargs)
        self.decimal_places = decimal_places

    def format_value(self, value, locale: str = "en"):
        if value is None:
            return None

        return format_decimal(value, locale, self.decimal_places)

    def parse_value(self, raw, locale: str = "en") -> Decimal | None:
        if raw is None or raw == "":
            return None

        if isinstance(raw, bool) or not isinstance(raw, (str, int, float, Decimal)):
            raise self._fail("validation.number-invalid")

        try:
            return parse_decimal(raw, locale)
        except DecimalParseError as error:
            raise self._fail("validation.number-invalid") from error


class DateField(AdminField):
    field_type = "date"

    def format_value(self, value, locale: str = "en"):
        if value is None:
            return None

        return format_date(value, locale)

    def parse_value(self, raw, locale: str = "en") -> date | None:
        if raw is None or raw == "":
            return None

        if not isinstance(raw, str):
            raise self._fail("validation.date-invalid")

        try:
            return parse_date(raw, locale)
        except ValueError as error:
            raise self._fail("validation.date-invalid") from error


class DateTimeField(AdminField):
    field_type = "datetime"

    def format_value(self, value, locale: str = "en"):
        if value is None:
            return None

        return format_datetime(value, locale)

    def parse_value(self, raw, locale: str = "en") -> datetime | None:
        if raw is None or raw == "":
            return None

        if not isinstance(raw, str):
            raise self._fail("validation.datetime-invalid")

        try:
            return parse_datetime(raw, locale)
        except ValueError as error:
            raise self._fail("validation.datetime-invalid") from error


class SelectField(AdminField):
    field_type = "select"

    def __init__(self, *args, choices: list[tuple[str, str]] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices = choices or []

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["choices"] = [{"value": value, "label": label} for value, label in self.choices]

        return schema

    def validate(self, value) -> None:
        super().validate(value)

        if value in (None, ""):
            return

        allowed = {choice for choice, _ in self.choices}

        if not isinstance(value, str) or value not in allowed:
            raise self._fail("validation.invalid")


class TimeField(AdminField):
    field_type = "time"

    def format_value(self, value, locale: str = "en"):
        if value is None:
            return None

        return format_time(value, locale)

    def parse_value(self, raw, locale: str = "en") -> time | None:
        if raw is None or raw == "":
            return None

        if not isinstance(raw, str):
            raise self._fail("validation.time-invalid")

        try:
            return parse_time(raw, locale)
        except ValueError as error:
            raise self._fail("validation.time-invalid") from error


_DEFAULT_SANITIZER = object()


class RichTextField(AdminField):
    field_type = "richtext"

    def __init__(self, *args, upload_url: str | None = None, sanitizer=_DEFAULT_SANITIZER, **kwargs):
        super().__init__(*args, **kwargs)
        self.upload_url = upload_url
        self._sanitizer = sanitize_html if sanitizer is _DEFAULT_SANITIZER else sanitizer

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["upload_url"] = self.upload_url

        return schema

    def parse_value(self, raw, locale: str = "en"):
        if raw is None or raw == "":
            return raw

        return self._sanitizer(raw) if self._sanitizer is not None else raw


class JsonField(AdminField):
    field_type = "json"

    def format_value(self, value, locale: str = "en"):
        if value is None:
            return None

        return json.dumps(value, ensure_ascii=False, indent=2)

    def parse_value(self, raw, locale: str = "en"):
        if raw is None or raw == "":
            return None

        if not isinstance(raw, str):
            return raw

        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise self._fail("validation.json-invalid") from error


class MultiSelectField(AdminField):
    field_type = "multiselect"

    def __init__(self, *args, choices: list[tuple[str, str]] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices = choices or []

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["choices"] = [{"value": value, "label": label} for value, label in self.choices]

        return schema

    def parse_value(self, raw, locale: str = "en") -> list:
        if raw is None or raw == "":
            return []

        if not isinstance(raw, (list, tuple)):
            raise self._fail("validation.invalid")

        return list(raw)

    def validate(self, value) -> None:
        if self.required and not value:
            raise self._fail("validation.required")

        allowed = {choice for choice, _ in self.choices}

        for item in value or []:
            if not isinstance(item, str) or item not in allowed:
                raise self._fail("validation.invalid")


class RelationField(AdminField):
    """Select whose options are records of another table.

    Options are resolved server-side by the owning resource's ``options_<name>``
    handler, which builds each option label however it wants. When ``depends_on``
    is set, the field is a dependent select: its options are filtered by the current
    values of the listed parent fields, and it resets whenever a parent changes.
    """

    field_type = "relation"

    def __init__(self, *args, depends_on: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.depends_on = list(depends_on or [])

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["depends_on"] = self.depends_on

        return schema

    def parse_value(self, raw, locale: str = "en"):
        if raw is None or raw == "":
            return None

        try:
            return int(raw)
        except (TypeError, ValueError) as error:
            raise self._fail("validation.integer-invalid") from error


class LookupField(RelationField):
    """Autocomplete relation: options are searched live as the user types.

    Options come from the same `options_<name>` handler, which receives the typed
    query under `q` and can decide both what to search and what label to show. It
    supports `depends_on` for cross-select filtering and preloads the current value.
    """

    field_type = "lookup"

    def __init__(self, *args, min_chars: int = 0, initial_limit: int = 10, search_limit: int = 20, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_chars = min_chars
        self.initial_limit = initial_limit
        self.search_limit = search_limit

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["min_chars"] = self.min_chars
        schema["initial_limit"] = self.initial_limit
        schema["search_limit"] = self.search_limit

        return schema


class ColorField(AdminField):
    field_type = "color"

    def validate(self, value) -> None:
        super().validate(value)

        if value not in (None, "") and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(value)):
            raise self._fail("validation.color-invalid")


class ImageField(AdminField):
    field_type = "image"

    def __init__(self, *args, upload_url: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.upload_url = upload_url

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["upload_url"] = self.upload_url

        return schema


class FileField(AdminField):
    field_type = "file"

    def __init__(self, *args, upload_url: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.upload_url = upload_url

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["upload_url"] = self.upload_url

        return schema


class TranslationsField(AdminField):
    """Virtual field editing a record's per-language content (title/body).

    The frontend loads the active languages and the current translations from the
    given URLs and saves them through ``save_url``. Not persisted as a model column.
    """

    field_type = "translations"

    def __init__(self, *args, languages_url: str, value_url: str, save_url: str, **kwargs):
        kwargs.setdefault("virtual", True)
        super().__init__(*args, **kwargs)
        self.languages_url = languages_url
        self.value_url = value_url
        self.save_url = save_url

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["languages_url"] = self.languages_url
        schema["value_url"] = self.value_url
        schema["save_url"] = self.save_url

        return schema


class PermissionMatrixField(AdminField):
    """Virtual field rendering permissions grouped by permission group as checkboxes.

    It is not persisted to the model. The frontend loads the grouped catalog and the
    current selection from the given endpoints and saves through ``save_url``.
    """

    field_type = "permission_matrix"

    def __init__(self, *args, groups_url: str, value_url: str, save_url: str, **kwargs):
        kwargs.setdefault("virtual", True)
        super().__init__(*args, **kwargs)
        self.groups_url = groups_url
        self.value_url = value_url
        self.save_url = save_url

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["groups_url"] = self.groups_url
        schema["value_url"] = self.value_url
        schema["save_url"] = self.save_url

        return schema
