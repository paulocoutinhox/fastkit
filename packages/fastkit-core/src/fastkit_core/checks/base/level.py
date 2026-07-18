from enum import Enum


class CheckLevel(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"
