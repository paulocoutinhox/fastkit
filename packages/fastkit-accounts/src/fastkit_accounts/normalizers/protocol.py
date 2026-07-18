from typing import Protocol, runtime_checkable


@runtime_checkable
class LoginIdentifierNormalizer(Protocol):
    type: str

    def normalize(self, value: str) -> str: ...

    def mask(self, value: str) -> str: ...

    def validate(self, value: str) -> None: ...
