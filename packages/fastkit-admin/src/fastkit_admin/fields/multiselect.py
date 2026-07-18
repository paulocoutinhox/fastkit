from fastkit_admin.fields.base import AdminField


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
