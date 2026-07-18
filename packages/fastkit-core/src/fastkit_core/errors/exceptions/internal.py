from fastkit_core.errors.codes import INTERNAL_ERROR
from fastkit_core.errors.exceptions.base import FastKitError


class InternalError(FastKitError):
    def __init__(self, message: str | None = None):
        super().__init__(INTERNAL_ERROR, message)
