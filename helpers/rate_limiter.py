"""How much one address may call, counted in something that never grows without a ceiling."""

from collections import OrderedDict
from typing import MutableMapping

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from throttled.fastapi import IPLimiter, TotalLimiter
from throttled.models import Rate
from throttled.storage.memory import MemoryStorage

from helpers.errors import build_payload
from helpers.i18n import translate
from helpers.settings import settings

CODE = "error.rate-limited"


class BoundedWindows(MutableMapping):
    """What the limiter counts in, holding the clients seen most recently and no more of them than it was given."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.windows: OrderedDict = OrderedDict()

    def __getitem__(self, key):
        # The library replaces an expired window on the next hit, so nothing here ever drops one that is still counting.
        self.windows.move_to_end(key)

        return self.windows[key]

    def __setitem__(self, key, value):
        self.windows[key] = value
        self.windows.move_to_end(key)

        while len(self.windows) > self.capacity:
            self.windows.popitem(last=False)

    def __delitem__(self, key):
        del self.windows[key]

    def __iter__(self):
        return iter(self.windows)

    def __len__(self):
        return len(self.windows)


def refused(exceeded) -> Response:
    """A refusal that happens before the application still answers what the application answers, which is the one shape every error of this side has."""
    return JSONResponse(status_code=exceeded.status_code, content=build_payload(CODE, translate(CODE)), headers=exceeded.headers)


def setup(app: FastAPI):
    if not settings.rate_limit.enabled:
        return

    # An address that stops calling is never hit again, and a plain dict would hold every one that ever called for as long as the process lives.
    storage = MemoryStorage(cache=BoundedWindows(settings.rate_limit.tracked_clients))

    total_limiter = TotalLimiter(limit=Rate(settings.rate_limit.total_limit, settings.rate_limit.total_window), storage=storage, response_factory=refused)
    ip_limiter = IPLimiter(limit=Rate(settings.rate_limit.ip_limit, settings.rate_limit.ip_window), storage=storage, response_factory=refused)

    app.add_middleware(BaseHTTPMiddleware, dispatch=total_limiter.dispatch)
    app.add_middleware(BaseHTTPMiddleware, dispatch=ip_limiter.dispatch)
