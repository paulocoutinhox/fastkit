from datetime import time

from fastkit_admin.fields.base import AdminField
from fastkit_admin.formatters import format_time, parse_time


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
