from fastkit_admin.fields.base import AdminField


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
