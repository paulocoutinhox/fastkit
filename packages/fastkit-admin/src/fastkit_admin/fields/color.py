import re

from fastkit_admin.fields.base import AdminField


class ColorField(AdminField):
    field_type = "color"

    def validate(self, value) -> None:
        super().validate(value)

        if value not in (None, "") and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(value)):
            raise self._fail("validation.color-invalid")
