from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Elsewhere:
    """A filter whose column lives on another table: the column is what the value is read through, and the condition is what it narrows the listing to."""

    column: object
    narrows: Callable
