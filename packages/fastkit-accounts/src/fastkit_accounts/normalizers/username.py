from fastkit_accounts.normalizers.failure import _fail


class UsernameNormalizer:
    type = "username"

    def normalize(self, value: str) -> str:
        return value.strip().lower()

    def mask(self, value: str) -> str:
        return value

    def validate(self, value: str) -> None:
        normalized = self.normalize(value)

        if len(normalized) < 3:
            raise _fail("value", "validation.username-too-short")
