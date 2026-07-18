from decimal import Decimal

from fastkit_admin.fields.base import AdminField
from fastkit_admin.formatters import DecimalParseError, format_decimal, parse_decimal


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
