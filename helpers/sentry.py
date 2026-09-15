"""Where a failure is reported, and nowhere when the environment names no place."""

import logging

import sentry_sdk

from helpers.settings import settings

logger = logging.getLogger(__name__)


def setup() -> bool:
    """An environment with no dsn reports nowhere, which is what keeps a development failure out of the tracker."""
    if not settings.sentry.dsn:
        # Saying so is what separates "not configured" from "running code that never knew about it".
        logger.info("[sentry] not reporting: %s carries no dsn", settings.environment)

        return False

    sentry_sdk.init(dsn=settings.sentry.dsn, environment=settings.environment, release=settings.version, traces_sample_rate=settings.sentry.traces_sample_rate, send_default_pii=settings.sentry.send_default_pii, include_local_variables=settings.sentry.include_local_variables)

    logger.info("[sentry] reporting as %s %s", settings.environment, settings.version)

    return True
