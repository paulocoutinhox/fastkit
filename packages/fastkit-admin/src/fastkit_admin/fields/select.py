from fastkit_admin.fields.base import AdminField


class SelectField(AdminField):
    field_type = "select"

    def __init__(self, *args, choices: list[tuple[str, str]] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices = choices or []

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["choices"] = [
            {"value": value, "label": label} for value, label in self.choices
        ]

        return schema

    def validate(self, value) -> None:
        super().validate(value)

        if value in (None, ""):
            return

        allowed = {choice for choice, _ in self.choices}

        if not isinstance(value, str) or value not in allowed:
            raise self._fail("validation.invalid")
