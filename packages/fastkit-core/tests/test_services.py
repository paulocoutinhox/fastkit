import asyncio

import pytest

from fastkit_core.services.container import Lifetime, ServiceContainer, ServiceError


class Database:
    pass


class Repo:
    def __init__(self, db):
        self.db = db


async def test_singleton_is_cached():
    container = ServiceContainer()
    container.register_singleton(Database, lambda scope: Database())

    scope = container.scope()
    first = await scope.get(Database)
    second = await container.scope().get(Database)

    assert first is second
    assert container.contains(Database)


async def test_transient_creates_each_time():
    container = ServiceContainer()
    container.register_transient(Database, lambda scope: Database())

    scope = container.scope()

    assert await scope.get(Database) is not await scope.get(Database)


async def test_scoped_is_shared_within_scope_only():
    container = ServiceContainer()
    container.register_scoped(Database, lambda scope: Database())

    scope = container.scope()

    assert await scope.get(Database) is await scope.get(Database)
    assert await scope.get(Database) is not await container.scope().get(Database)


async def test_scoped_concurrent_resolution_creates_a_single_instance():
    created = []

    async def factory(scope):
        await asyncio.sleep(0)
        instance = Database()
        created.append(instance)

        return instance

    container = ServiceContainer()
    container.register_scoped(Database, factory)
    scope = container.scope()

    first, second = await asyncio.gather(scope.get(Database), scope.get(Database))

    assert first is second
    assert len(created) == 1


async def test_async_factory_and_dependency_resolution():
    container = ServiceContainer()

    async def make_db(scope):
        return Database()

    container.register_singleton(Database, make_db)
    container.register_transient(Repo, lambda scope: Repo(None))

    repo = await container.scope().get(Repo)

    assert isinstance(repo, Repo)


async def test_override_replaces_singleton():
    container = ServiceContainer()
    container.register_singleton(Database, lambda scope: Database())

    original = await container.scope().get(Database)
    container.override(Database, lambda scope: Database())

    assert await container.scope().get(Database) is not original


async def test_unregistered_service_raises():
    container = ServiceContainer()

    with pytest.raises(ServiceError, match="not registered"):
        await container.scope().get(Database)

    with pytest.raises(ServiceError, match="not registered"):
        await container.get_singleton(Database)


async def test_circular_dependency_detected():
    container = ServiceContainer()

    async def make_a(scope):
        return await scope.get(Repo)

    async def make_b(scope):
        return await scope.get(Database)

    container.register_singleton(Database, make_a)
    container.register_singleton(Repo, make_b)

    with pytest.raises(ServiceError, match="circular"):
        await container.scope().get(Database)


async def test_transient_circular_dependency_detected():
    container = ServiceContainer()

    async def make_a(scope):
        return await scope.get(Repo)

    async def make_b(scope):
        return await scope.get(Database)

    container.register_transient(Database, make_a)
    container.register_transient(Repo, make_b)

    with pytest.raises(ServiceError, match="circular"):
        await container.scope().get(Database)


async def test_shutdown_runs_callbacks_in_reverse():
    container = ServiceContainer()
    order: list[int] = []

    async def first():
        order.append(1)

    async def second():
        order.append(2)

    container.add_shutdown(first)
    container.add_shutdown(second)
    await container.shutdown()

    assert order == [2, 1]


def test_register_default_lifetime_is_singleton():
    container = ServiceContainer()
    container.register(Database, lambda scope: Database())

    assert container._registrations[Database].lifetime is Lifetime.singleton


async def test_concurrent_singleton_creation_builds_once():
    import asyncio

    container = ServiceContainer()
    calls = {"n": 0}

    async def factory(scope):
        calls["n"] += 1
        await asyncio.sleep(0)
        return Database()

    container.register_singleton(Database, factory)

    results = await asyncio.gather(
        *[container.get_singleton(Database) for _ in range(8)]
    )

    assert calls["n"] == 1
    assert all(result is results[0] for result in results)


async def test_singleton_dependency_chain_resolves():
    container = ServiceContainer()
    container.register_singleton(Database, lambda scope: Database())
    container.register_singleton(Repo, lambda scope: _build_repo(scope))

    async def _build_repo(scope):
        return Repo(await scope.get(Database))

    repo = await container.get_singleton(Repo)

    assert isinstance(repo.db, Database)
