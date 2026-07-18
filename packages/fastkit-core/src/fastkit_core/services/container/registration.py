from typing import Any, Callable

from fastkit_core.services.container.lifetime import Lifetime


class ServiceRegistration:
    def __init__(self, key: type, factory: Callable[..., Any], lifetime: Lifetime):
        self.key = key
        self.factory = factory
        self.lifetime = lifetime
