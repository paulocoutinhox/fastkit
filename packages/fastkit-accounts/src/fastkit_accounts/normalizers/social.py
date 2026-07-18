from fastkit_accounts.normalizers.failure import _fail


class SocialNormalizer:
    """Identifier for a social login as 'provider:external_id', e.g. 'google:12345'."""

    def __init__(self, provider: str):
        self.type = provider

    def normalize(self, value: str) -> str:
        return f"{self.type}:{value.strip()}"

    def mask(self, value: str) -> str:
        return f"{self.type}:***"

    def validate(self, value: str) -> None:
        if not value.strip():
            raise _fail("value", "validation.social-invalid")
