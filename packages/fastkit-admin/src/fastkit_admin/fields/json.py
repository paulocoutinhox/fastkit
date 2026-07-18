import json

from fastkit_admin.fields.base import AdminField


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
