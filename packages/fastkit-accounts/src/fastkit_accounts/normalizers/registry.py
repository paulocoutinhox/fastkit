from fastkit_accounts.normalizers.cnpj import CnpjNormalizer
from fastkit_accounts.normalizers.cpf import CpfNormalizer
from fastkit_accounts.normalizers.email import EmailNormalizer
from fastkit_accounts.normalizers.phone import PhoneNormalizer
from fastkit_accounts.normalizers.protocol import LoginIdentifierNormalizer
from fastkit_accounts.normalizers.social import SocialNormalizer
from fastkit_accounts.normalizers.username import UsernameNormalizer

DEFAULT_SOCIAL_PROVIDERS = ("google", "facebook", "apple")


class NormalizerRegistry:
    """Holds one normalizer per identifier type and applies it consistently."""

    def __init__(self):
        self._by_type: dict[str, LoginIdentifierNormalizer] = {}

    def register(self, normalizer: LoginIdentifierNormalizer) -> None:
        self._by_type[normalizer.type] = normalizer

    def types(self) -> list[str]:
        return sorted(self._by_type)

    def get(self, identifier_type: str) -> LoginIdentifierNormalizer:
        normalizer = self._by_type.get(identifier_type)

        if normalizer is None:
            raise KeyError(
                f"no normalizer registered for identifier type '{identifier_type}'"
            )

        return normalizer

    def normalize(self, identifier_type: str, value: str) -> str:
        return self.get(identifier_type).normalize(value)


def default_registry() -> NormalizerRegistry:
    registry = NormalizerRegistry()

    for normalizer in (
        EmailNormalizer(),
        UsernameNormalizer(),
        PhoneNormalizer(),
        CpfNormalizer(),
        CnpjNormalizer(),
    ):
        registry.register(normalizer)

    for provider in DEFAULT_SOCIAL_PROVIDERS:
        registry.register(SocialNormalizer(provider))

    return registry
