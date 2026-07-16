import re
import unicodedata
from typing import Protocol, runtime_checkable

from fastkit_core.errors.codes import VALIDATION_FAILED
from fastkit_core.errors.exceptions import FieldError, ValidationError

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@runtime_checkable
class LoginIdentifierNormalizer(Protocol):
    type: str

    def normalize(self, value: str) -> str:
        ...

    def mask(self, value: str) -> str:
        ...

    def validate(self, value: str) -> None:
        ...


def _fail(field: str, code: str) -> ValidationError:
    return ValidationError(VALIDATION_FAILED, field_errors=[FieldError(field=field, code=code)])


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


class CnpjNormalizer:
    type = "cnpj"

    def normalize(self, value: str) -> str:
        return re.sub(r"\D", "", value)

    def mask(self, value: str) -> str:
        digits = self.normalize(value)

        return f"**.***.***/{digits[8:12]}-{digits[12:]}" if len(digits) == 14 else "***"

    def validate(self, value: str) -> None:
        if len(self.normalize(value)) != 14:
            raise _fail("value", "validation.cnpj-invalid")


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
            raise KeyError(f"no normalizer registered for identifier type '{identifier_type}'")

        return normalizer

    def normalize(self, identifier_type: str, value: str) -> str:
        return self.get(identifier_type).normalize(value)


DEFAULT_SOCIAL_PROVIDERS = ("google", "facebook", "apple")


def default_registry() -> NormalizerRegistry:
    registry = NormalizerRegistry()

    for normalizer in (EmailNormalizer(), UsernameNormalizer(), PhoneNormalizer(), CpfNormalizer(), CnpjNormalizer()):
        registry.register(normalizer)

    for provider in DEFAULT_SOCIAL_PROVIDERS:
        registry.register(SocialNormalizer(provider))

    return registry
