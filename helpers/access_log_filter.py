"""Removes query credentials from the structured Uvicorn access log."""

import logging


class AccessLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        client, method, target, version, status = record.args
        record.args = (client, method, target.partition("?")[0], version, status)

        return True
