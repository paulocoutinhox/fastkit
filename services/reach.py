from dataclasses import dataclass


@dataclass(frozen=True)
class Reach:
    """How a resource with no tenant of its own is confined, which is always the row it belongs to: the key it points with, the model it points at, and how that one reaches a tenant when it carries none either."""

    column: object
    parent: type
    through: "Reach | None" = None
