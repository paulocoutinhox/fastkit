from fastkit_accounts.normalizers.cnpj import CnpjNormalizer
from fastkit_accounts.normalizers.cpf import CpfNormalizer
from fastkit_accounts.normalizers.email import EMAIL_PATTERN, EmailNormalizer
from fastkit_accounts.normalizers.failure import _fail
from fastkit_accounts.normalizers.phone import PhoneNormalizer
from fastkit_accounts.normalizers.protocol import LoginIdentifierNormalizer
from fastkit_accounts.normalizers.registry import (
    DEFAULT_SOCIAL_PROVIDERS,
    NormalizerRegistry,
    default_registry,
)
from fastkit_accounts.normalizers.social import SocialNormalizer
from fastkit_accounts.normalizers.username import UsernameNormalizer

__all__ = [
    "DEFAULT_SOCIAL_PROVIDERS",
    "EMAIL_PATTERN",
    "CnpjNormalizer",
    "CpfNormalizer",
    "EmailNormalizer",
    "LoginIdentifierNormalizer",
    "NormalizerRegistry",
    "PhoneNormalizer",
    "SocialNormalizer",
    "UsernameNormalizer",
    "_fail",
    "default_registry",
]
