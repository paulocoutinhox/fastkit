import re

from fastkit_accounts.normalizers.failure import _fail


class CnpjNormalizer:
    type = "cnpj"

    def normalize(self, value: str) -> str:
        return re.sub(r"\D", "", value)

    def mask(self, value: str) -> str:
        digits = self.normalize(value)

        return (
            f"**.***.***/{digits[8:12]}-{digits[12:]}" if len(digits) == 14 else "***"
        )

    def validate(self, value: str) -> None:
        if len(self.normalize(value)) != 14:
            raise _fail("value", "validation.cnpj-invalid")
