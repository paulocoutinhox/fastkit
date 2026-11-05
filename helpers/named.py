"""Puts the name of the request on every line, so what one call did is read together instead of hunted for."""

import logging

from helpers.tracing import current_request


class Named(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request = current_request.get() or "-"

        return True
