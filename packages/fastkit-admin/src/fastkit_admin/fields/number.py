from fastkit_admin.fields.base import AdminField


class NumberField(AdminField):
    field_type = "number"

    def parse_value(self, raw, locale: str = "en"):
        if raw is None or raw == "":
            return None

        try:
            return int(raw)
        except (TypeError, ValueError) as error:
            raise self._fail("validation.integer-invalid") from error
