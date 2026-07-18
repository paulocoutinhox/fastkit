import asyncio
from typing import Any

from fastkit_core.services.container.container import ServiceContainer
from fastkit_core.services.container.lifetime import Lifetime
from fastkit_core.services.container.errors import ServiceError


class ServiceScope:
    def __init__(self, container: ServiceContainer):
        self._container = container
        self._scoped: dict[type, Any] = {}
        self._locks: dict[type, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _lock_for(self, key: type) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(key)

            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock

            return lock

    async def get(self, key: type) -> Any:
        registration = self._container._registrations.get(key)

        if registration is None:
            raise ServiceError(f"service {key.__name__} is not registered")

        if registration.lifetime is Lifetime.singleton:
            return await self._container.get_singleton(key)

        if registration.lifetime is Lifetime.scoped:
            if key in self._scoped:
                return self._scoped[key]

            async with await self._lock_for(key):
                if key not in self._scoped:
                    self._scoped[key] = await self._container._create(
                        registration, self
                    )

                return self._scoped[key]

        return await self._container._create(registration, self)
