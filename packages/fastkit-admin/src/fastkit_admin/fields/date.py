from datetime import date

from fastkit_admin.fields.base import AdminField
from fastkit_admin.formatters import format_date, parse_date


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
