from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from fastkit_core.errors.codes import VALIDATION_FAILED
from fastkit_core.errors.exceptions import FieldError, ValidationError


class PasswordHashService:
    """Argon2id hashing with transparent rehash and a configurable strength policy."""

    def __init__(self, min_length: int = 12, max_length: int = 128):
        self._hasher = PasswordHasher()
        self._min_length = min_length
        self._max_length = max_length
        self._dummy_hash = None

    def enforce_policy(self, password: str) -> None:
        if len(password) < self._min_length:
            raise ValidationError(
                VALIDATION_FAILED,
                field_errors=[FieldError("password", "validation.password-too-short", params={"min_length": self._min_length})],
            )

        if len(password) > self._max_length:
            raise ValidationError(
                VALIDATION_FAILED,
                field_errors=[FieldError("password", "validation.password-too-long", params={"max_length": self._max_length})],
            )

    def hash(self, password: str) -> str:
        self.enforce_policy(password)

        return self._hasher.hash(password)

    def rehash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            self._hasher.verify(password_hash, password)

            return True
        except (VerifyMismatchError, InvalidHashError):
            return False

    def dummy_verify(self, password: str) -> None:
        """Run a verify against a throwaway hash so an unknown identifier costs the same as a known one."""

        if self._dummy_hash is None:
            self._dummy_hash = self._hasher.hash("fastkit-timing-guard")

        self.verify(self._dummy_hash, password)

    def needs_rehash(self, password_hash: str) -> bool:
        return self._hasher.check_needs_rehash(password_hash)
