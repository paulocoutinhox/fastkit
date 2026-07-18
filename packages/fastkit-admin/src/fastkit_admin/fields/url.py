import re

from fastkit_admin.fields.text import TextField


class URLField(TextField):
    field_type = "url"

    def validate(self, value) -> None:
        super().validate(value)

        if value not in (None, "") and not re.fullmatch(r"https?://[^\s]+", str(value)):
            raise self._fail("validation.url-invalid")
