import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("fastkit.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs one structured line per request with method, path, status and duration."""

    async def dispatch(self, request, call_next):
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.exception("request failed %s %s (%sms)", request.method, request.url.path, duration_ms)
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info("request %s %s -> %s (%sms)", request.method, request.url.path, response.status_code, duration_ms)

        return response
