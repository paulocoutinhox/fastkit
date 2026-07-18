import re

from fastkit_accounts.normalizers.failure import _fail


class CpfNormalizer:
    type = "cpf"

    def normalize(self, value: str) -> str:
        return re.sub(r"\D", "", value)

    def mask(self, value: str) -> str:
        digits = self.normalize(value)

        return f"***.***.{digits[6:9]}-{digits[9:]}" if len(digits) == 11 else "***"

    def validate(self, value: str) -> None:
        if len(self.normalize(value)) != 11:
            raise _fail("value", "validation.cpf-invalid")
