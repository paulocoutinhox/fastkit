import re
import unicodedata

from fastkit_accounts.normalizers.failure import _fail

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailNormalizer:
    type = "email"

    def normalize(self, value: str) -> str:
        return unicodedata.normalize("NFKC", value).strip().lower()

    def mask(self, value: str) -> str:
        name, _, domain = value.partition("@")
        head = name[0] if name else "*"

        return f"{head}***@{domain}"

    def validate(self, value: str) -> None:
        if not EMAIL_PATTERN.match(self.normalize(value)):
            raise _fail("value", "validation.email-invalid")
