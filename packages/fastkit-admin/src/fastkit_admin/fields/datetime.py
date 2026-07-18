from datetime import datetime

from fastkit_admin.fields.base import AdminField
from fastkit_admin.formatters import format_datetime, parse_datetime


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
