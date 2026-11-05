from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dependent:
    """A table that must go before its parent."""

    model: type
    field: str
    dependents: tuple["Dependent", ...] = field(default_factory=tuple)
