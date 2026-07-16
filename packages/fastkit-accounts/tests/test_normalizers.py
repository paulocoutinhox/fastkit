import pytest

from fastkit_core.errors.exceptions import ValidationError
from fastkit_accounts.normalizers import (
    CpfNormalizer,
    EmailNormalizer,
    NormalizerRegistry,
    PhoneNormalizer,
    UsernameNormalizer,
    default_registry,
)


def test_email_normalizer():
    normalizer = EmailNormalizer()

    assert normalizer.normalize("  User@Example.COM ") == "user@example.com"
    assert normalizer.mask("user@example.com") == "u***@example.com"
    normalizer.validate("user@example.com")

    with pytest.raises(ValidationError):
        normalizer.validate("not-an-email")


def test_email_mask_without_local_part():
    assert EmailNormalizer().mask("@example.com").startswith("*")


def test_username_normalizer():
    normalizer = UsernameNormalizer()

    assert normalizer.normalize("  Alice ") == "alice"
    assert normalizer.mask("alice") == "alice"
    normalizer.validate("alice")

    with pytest.raises(ValidationError):
        normalizer.validate("ab")


def test_phone_normalizer():
    normalizer = PhoneNormalizer()

    assert normalizer.normalize("(11) 98888-7777") == "+11988887777"
    assert normalizer.normalize("+551199998888") == "+551199998888"
    assert normalizer.mask("+551199998888").endswith("88")
    normalizer.validate("+5511988887777")

    with pytest.raises(ValidationError):
        normalizer.validate("123")


def test_cpf_normalizer():
    normalizer = CpfNormalizer()

    assert normalizer.normalize("123.456.789-09") == "12345678909"
    assert normalizer.mask("123.456.789-09") == "***.***.789-09"
    assert normalizer.mask("123") == "***"
    normalizer.validate("123.456.789-09")

    with pytest.raises(ValidationError):
        normalizer.validate("123")


def test_cnpj_normalizer():
    from fastkit_accounts.normalizers import CnpjNormalizer

    normalizer = CnpjNormalizer()

    assert normalizer.normalize("12.345.678/0001-95") == "12345678000195"
    assert normalizer.mask("12.345.678/0001-95") == "**.***.***/0001-95"
    assert normalizer.mask("123") == "***"
    normalizer.validate("12.345.678/0001-95")

    with pytest.raises(ValidationError):
        normalizer.validate("123")


def test_social_normalizer():
    from fastkit_accounts.normalizers import SocialNormalizer

    normalizer = SocialNormalizer("google")

    assert normalizer.type == "google"
    assert normalizer.normalize("  12345 ") == "google:12345"
    assert normalizer.mask("12345") == "google:***"
    normalizer.validate("12345")

    with pytest.raises(ValidationError):
        normalizer.validate("  ")


def test_default_registry_has_social_and_cnpj():
    registry = default_registry()

    assert registry.get("cnpj").type == "cnpj"
    assert registry.get("google").type == "google"
    assert registry.normalize("google", "abc") == "google:abc"


def test_registry_lookup_and_error():
    registry = default_registry()

    assert registry.normalize("email", "A@B.CO") == "a@b.co"

    with pytest.raises(KeyError, match="no normalizer registered"):
        registry.get("unknown")


def test_registry_registration():
    registry = NormalizerRegistry()
    registry.register(EmailNormalizer())

    assert registry.get("email").type == "email"
