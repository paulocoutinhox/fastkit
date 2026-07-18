from enum import Enum


class Lifetime(str, Enum):
    singleton = "singleton"
    scoped = "scoped"
    transient = "transient"
