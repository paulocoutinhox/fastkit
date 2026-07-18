import asyncio
import contextvars
import inspect
from typing import Any, Awaitable, Callable

from fastkit_core.services.container.lifetime import Lifetime
from fastkit_core.services.container.errors import ServiceError
from fastkit_core.services.container.registration import ServiceRegistration

_resolving_chain: contextvars.ContextVar[set | None] = contextvars.ContextVar(
    "fastkit_resolving_chain", default=None
)


class ServiceContainer:
    """Async-aware container supporting singleton, scoped and transient lifetimes with ordered shutdown."""

    def __init__(self):
        self._registrations: dict[type, ServiceRegistration] = {}
        self._singletons: dict[type, Any] = {}
        self._shutdowns: list[Callable[[], Awaitable[None]]] = []
        self._locks: dict[type, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    def register(
        self,
        key: type,
        factory: Callable[..., Any],
        lifetime: Lifetime = Lifetime.singleton,
    ) -> None:
        self._registrations[key] = ServiceRegistration(key, factory, lifetime)

    def register_singleton(self, key: type, factory: Callable[..., Any]) -> None:
        self.register(key, factory, Lifetime.singleton)

    def register_scoped(self, key: type, factory: Callable[..., Any]) -> None:
        self.register(key, factory, Lifetime.scoped)

    def register_transient(self, key: type, factory: Callable[..., Any]) -> None:
        self.register(key, factory, Lifetime.transient)

    def override(
        self,
        key: type,
        factory: Callable[..., Any],
        lifetime: Lifetime = Lifetime.singleton,
    ) -> None:
        self._singletons.pop(key, None)
        self.register(key, factory, lifetime)

    def contains(self, key: type) -> bool:
        return key in self._registrations

    def scope(self):
        from fastkit_core.services.container.scope import ServiceScope

        return ServiceScope(self)

    async def _create(self, registration: ServiceRegistration, scope) -> Any:
        chain = _resolving_chain.get()
        owns_chain = chain is None

        if owns_chain:
            chain = set()
            token = _resolving_chain.set(chain)

        if registration.key in chain:
            raise ServiceError(
                f"circular dependency detected while resolving {registration.key.__name__}"
            )

        chain.add(registration.key)

        try:
            result = registration.factory(scope)

            if inspect.isawaitable(result):
                result = await result

            return result
        finally:
            chain.discard(registration.key)

            if owns_chain:
                _resolving_chain.reset(token)

    async def _lock_for(self, key: type) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(key)

            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock

            return lock

    async def get_singleton(self, key: type) -> Any:
        if key in self._singletons:
            return self._singletons[key]

        registration = self._registrations.get(key)

        if registration is None:
            raise ServiceError(f"service {key.__name__} is not registered")

        chain = _resolving_chain.get()

        if chain is not None and key in chain:
            raise ServiceError(
                f"circular dependency detected while resolving {key.__name__}"
            )

        lock = await self._lock_for(key)

        async with lock:
            if key in self._singletons:
                return self._singletons[key]

            instance = await self._create(registration, self.scope())
            self._singletons[key] = instance

            return instance

    def add_shutdown(self, callback: Callable[[], Awaitable[None]]) -> None:
        self._shutdowns.append(callback)

    async def shutdown(self) -> None:
        while self._shutdowns:
            callback = self._shutdowns.pop()
            await callback()

        self._singletons.clear()
