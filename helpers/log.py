"""How this process writes down what it did."""

import logging

from helpers.access_log_filter import AccessLogFilter
from helpers.named import Named
from helpers.settings import settings

# These report every statement or tick they run, which would bury the application log in development.
QUIET_LOGGERS = {"aiosqlite": logging.WARNING, "aiomysql": logging.WARNING, "aiobotocore": logging.WARNING, "botocore": logging.WARNING, "boto3": logging.WARNING, "urllib3": logging.WARNING, "asyncio": logging.WARNING, "queuefy": logging.INFO}


access_log_filter = AccessLogFilter()


def setup():
    # Force makes this the configuration that wins, whoever touched logging before it.
    logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO, format="%(asctime)s %(levelname)s %(name)s [%(request)s] %(message)s", force=True)

    for handler in logging.getLogger().handlers:
        handler.addFilter(Named())

    for name, level in QUIET_LOGGERS.items():
        logging.getLogger(name).setLevel(level)

    logging.getLogger("uvicorn.access").addFilter(access_log_filter)

    # SQL reaches the log through ECHO_SQL, which sets its own level, and never through the root one.
    if not settings.database.echo:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
