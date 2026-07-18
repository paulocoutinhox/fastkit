import re

from fastkit_accounts.normalizers.failure import _fail


class PhoneNormalizer:
    type = "phone"

    def normalize(self, value: str) -> str:
        digits = re.sub(r"[^\d+]", "", value)

        if not digits.startswith("+"):
            digits = f"+{digits}"

        return digits

    def mask(self, value: str) -> str:
        normalized = self.normalize(value)

        return f"{normalized[:3]}****{normalized[-2:]}"

    def validate(self, value: str) -> None:
        normalized = self.normalize(value)

        if not re.fullmatch(r"\+\d{8,15}", normalized):
            raise _fail("value", "validation.phone-invalid")
