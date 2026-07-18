import re

from fastkit_admin.fields.text import TextField


class EmailField(TextField):
    field_type = "email"

    def validate(self, value) -> None:
        super().validate(value)

        if value not in (None, "") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value)):
            raise self._fail("validation.email-invalid")
