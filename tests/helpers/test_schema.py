"""The schema is built under a lock of the session wherever more than one copy can build it at once."""

import pytest
from sqlalchemy import event

from helpers import schema
from helpers.db import DROP_DIALECTS, async_engine

LOCK = schema.SchemaLock("SELECT 1 /* take */", "SELECT 1 /* release */")


@pytest.fixture
def statements():
    heard = []

    def listen(connection, cursor, statement, *rest):
        heard.append(statement)

    event.listen(async_engine.sync_engine, "before_cursor_execute", listen)
    yield heard
    event.remove(async_engine.sync_engine, "before_cursor_execute", listen)


async def test_a_server_database_builds_the_schema_holding_its_lock_and_gives_it_back(monkeypatch, statements):
    monkeypatch.setitem(schema.SCHEMA_LOCKS, "sqlite", LOCK)

    await schema.run_schema(lambda connection: statements.append("built"))

    assert statements == [LOCK.take, "built", LOCK.release]


async def test_the_lock_is_given_back_when_the_building_fails(monkeypatch, statements):
    monkeypatch.setitem(schema.SCHEMA_LOCKS, "sqlite", LOCK)

    def failing(connection):
        raise ValueError("a table nobody can build")

    with pytest.raises(ValueError):
        await schema.run_schema(failing)

    assert statements == [LOCK.take, LOCK.release]


async def test_a_lock_another_copy_kept_is_a_refusal_and_never_a_build_over_it(monkeypatch):
    built = []
    monkeypatch.setitem(schema.SCHEMA_LOCKS, "sqlite", schema.SchemaLock("SELECT 0", "SELECT 1"))

    with pytest.raises(RuntimeError):
        await schema.run_schema(built.append)

    assert built == []


def test_every_dialect_the_engine_can_drop_says_how_it_locks_the_schema():
    assert set(schema.SCHEMA_LOCKS) == set(DROP_DIALECTS)
