from enum import Enum


class CircuitState(str, Enum):
    closed = "closed"
    open = "open"
    half_open = "half_open"
