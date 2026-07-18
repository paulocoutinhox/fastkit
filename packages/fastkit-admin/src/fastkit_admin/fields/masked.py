import re

from fastkit_admin.fields.text import TextField


class MaskedField(TextField):
    field_type = "masked"

    def __init__(self, *args, mask: str, pattern: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mask = mask
        self.pattern = pattern

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["mask"] = self.mask
        schema["pattern"] = self.pattern

        return schema

    def validate(self, value) -> None:
        super().validate(value)

        if (
            value not in (None, "")
            and self.pattern is not None
            and not re.fullmatch(self.pattern, str(value))
        ):
            raise self._fail("validation.pattern-invalid")
