from dataclasses import dataclass


@dataclass(frozen=True)
class Credential:
    """A secret this gateway needs, under the name its own panel gives it and in a column named after the gateway."""

    field: str
    label: str
    hint: str
    role: str | None = None
