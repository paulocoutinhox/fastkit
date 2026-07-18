from fastkit_admin.fields.base import AdminField


class TextField(AdminField):
    field_type = "text"

    def __init__(self, *args, max_length: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_length = max_length

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["max_length"] = self.max_length

        return schema

    def validate(self, value) -> None:
        super().validate(value)

        if (
            value is not None
            and self.max_length is not None
            and len(str(value)) > self.max_length
        ):
            raise self._fail("validation.string-max-length")
