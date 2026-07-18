from fastkit_core.sanitize import sanitize_html
from fastkit_admin.fields.base import AdminField

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
